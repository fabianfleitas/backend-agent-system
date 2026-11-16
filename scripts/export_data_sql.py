#!/usr/bin/env python3
"""Export data-only de la base Supabase a un archivo .sql (RNF-06).

No requiere DATABASE_URL: lee los datos via REST/PostgREST usando
SUPABASE_URL + SUPABASE_SECRET_KEY, y genera sentencias INSERT restaurables
con `psql` o el SQL Editor de Supabase.

Uso:
    python3 scripts/export_data_sql.py
    python3 scripts/export_data_sql.py --output backups/mi_backup.sql
    python3 scripts/export_data_sql.py --no-embeddings
    python3 scripts/export_data_sql.py --tables app_users,instituciones

Notas:
- Solo datos: no incluye estructura, enums, funciones, policies RLS ni grants.
- Los id son GENERATED ALWAYS AS IDENTITY: se emiten con OVERRIDING SYSTEM VALUE.
- Se resetean las secuencias con setval() al final.
- El ciclo mensajes.audit_id <-> audit_logs.mensaje_id se resuelve insertando
  mensajes con audit_id=NULL y un UPDATE posterior.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAGE_SIZE = 1000
REST_PATH = "rest/v1"

# Orden topologico de FKs. `__mensajes_audit_null__` y `__update_mensajes_audit__`
# marcan el tratamiento especial del ciclo mensajes <-> audit_logs.
TABLE_ORDER = [
    "app_users",
    "instituciones",
    "institucion_miembros",
    "platform_admins",
    "planes",
    "categorias",
    "documentos",
    "documento_versiones",
    "document_chunks",
    "document_embeddings",
    "conversaciones",
    "__mensajes_audit_null__",
    "audit_logs",
    "__update_mensajes_audit__",
    "message_documents",
    "feedback",
    "audio_interactions",
    "pii_mappings",
    "suscripciones",
    "suscripcion_historial",
    "pagos",
    "comprobantes",
    "stripe_eventos",
    "notificaciones",
    "configuracion_smtp",
    "plantillas_email",
    "config_parametros",
]

# audit_logs usa uuid (no identity) como PK; el resto usa bigint identity.
NON_IDENTITY_TABLES = {"audit_logs"}

# Columnas que requieren cast explicito (extraidas de all_tables.json + vector).
JSONB_COLUMNS = {
    ("planes", "features"),
    ("stripe_eventos", "payload"),
    ("notificaciones", "datos"),
}
VECTOR_COLUMNS = {("document_embeddings", "embedding")}


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def normalize_url(raw: str) -> str:
    url = raw.strip().rstrip("/")
    return re.sub(r"/rest/v1$", "", url)


def sql_literal(value: object, table: str, column: str) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (dict, list)):
        return f"'{escape_text(json.dumps(value, ensure_ascii=False))}'::jsonb"
    text = str(value)
    if (table, column) in VECTOR_COLUMNS:
        return f"'{escape_text(text)}'::extensions.vector"
    if (table, column) in JSONB_COLUMNS:
        return f"'{escape_text(text)}'::jsonb"
    return f"'{escape_text(text)}'"


def escape_text(text: str) -> str:
    return text.replace("'", "''")


def fetch_table(
    client: httpx.Client, url: str, headers: dict[str, str], table: str
) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        end = offset + PAGE_SIZE - 1
        resp = client.get(
            f"{url}/{REST_PATH}/{table}",
            params={"select": "*", "order": "id.asc"},
            headers={**headers, "Range": f"{offset}-{end}"},
        )
        if resp.status_code == 404:
            print(f"  ! tabla no existe (404), se omite: {table}", file=sys.stderr)
            return []
        resp.raise_for_status()
        page = resp.json()
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def insert_statement(table: str, row: dict) -> str:
    columns = list(row.keys())
    values = ", ".join(sql_literal(row[c], table, c) for c in columns)
    cols = ", ".join(f'"{c}"' for c in columns)
    override = "" if table in NON_IDENTITY_TABLES else " OVERRIDING SYSTEM VALUE"
    return f'INSERT INTO public."{table}" ({cols}){override} VALUES ({values});'


def sequence_reset(table: str, has_rows: bool) -> str | None:
    if not has_rows or table in NON_IDENTITY_TABLES:
        return None
    return (
        f"SELECT setval(pg_get_serial_sequence('public.{table}', 'id'), "
        f"(SELECT COALESCE(MAX(id), 1) FROM public.{table}));"
    )


def build_backup(args: argparse.Namespace) -> Path:
    env = load_env(PROJECT_ROOT / ".env")
    url = normalize_url(env.get("SUPABASE_URL", ""))
    key = env.get("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        raise SystemExit("ERROR: faltan SUPABASE_URL / SUPABASE_SECRET_KEY en .env")

    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    output = Path(args.output) if args.output else (
        PROJECT_ROOT / "backups" / f"backup_data_{datetime.now():%Y%m%d_%H%M%S}.sql"
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    selected = set(args.tables.split(",")) if args.tables else None
    excluded = set(args.exclude.split(",")) if args.exclude else set()
    if args.no_embeddings:
        excluded.add("document_embeddings")

    lines: list[str] = [
        "-- Backup data-only generado por scripts/export_data_sql.py",
        f"-- Fecha: {datetime.now().isoformat(timespec='seconds')}",
        f"-- Origen: {url}",
        "-- Solo datos. Requiere el esquema (tablas, enums, tipos) ya existente.",
        "-- Restaurar con: psql <datasource> -f <este_archivo.sql>",
        "",
        "BEGIN;",
        "",
    ]
    counts: dict[str, int] = {}
    pending_audit_updates: list[tuple[int, str]] = []

    with httpx.Client(timeout=120) as client:
        for table in TABLE_ORDER:
            if table == "__mensajes_audit_null__":
                if selected and "mensajes" not in selected:
                    continue
                rows = fetch_table(client, url, headers, "mensajes")
                counts["mensajes"] = len(rows)
                lines.append(f"-- mensajes ({len(rows)} filas; audit_id diferido)")
                for row in rows:
                    audit_id = row.get("audit_id")
                    if audit_id:
                        pending_audit_updates.append((row["id"], audit_id))
                    row = {**row, "audit_id": None}
                    lines.append(insert_statement("mensajes", row))
                lines.append(sequence_reset("mensajes", bool(rows)) or "")
                lines.append("")
                continue
            if table == "__update_mensajes_audit__":
                if not pending_audit_updates:
                    continue
                lines.append("-- Restaurar mensajes.audit_id (ciclo con audit_logs)")
                for mensaje_id, audit_id in pending_audit_updates:
                    lines.append(
                        f'UPDATE public."mensajes" SET "audit_id" = '
                        f"'{escape_text(str(audit_id))}' WHERE \"id\" = {mensaje_id};"
                    )
                lines.append("")
                continue

            if table in excluded:
                print(f"  - omitida por flag: {table}", file=sys.stderr)
                continue
            if selected and table not in selected:
                continue

            rows = fetch_table(client, url, headers, table)
            counts[table] = len(rows)
            if not rows:
                continue
            lines.append(f"-- {table} ({len(rows)} filas)")
            for row in rows:
                lines.append(insert_statement(table, row))
            reset = sequence_reset(table, bool(rows))
            if reset:
                lines.append(reset)
            lines.append("")

    lines.append("COMMIT;")
    lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")
    total = sum(counts.values())
    print(f"Backup OK: {output} ({output.stat().st_size} bytes, {total} filas)")
    print("Tablas:", ", ".join(f"{t}={n}" for t, n in counts.items()))
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="ruta del .sql de salida")
    parser.add_argument("--tables", help="lista separada por comas de tablas a exportar")
    parser.add_argument("--exclude", help="lista separada por comas de tablas a excluir")
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="no exportar document_embeddings (archivo mucho mas liviano)",
    )
    args = parser.parse_args()
    try:
        build_backup(args)
    except httpx.HTTPError as exc:
        print(f"ERROR HTTP: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
