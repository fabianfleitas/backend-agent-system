#!/usr/bin/env python3
"""Crea un usuario e institución sintéticos en un Supabase local desechable.

Este script no debe apuntar a producción. Toma las claves locales desde el
archivo generado por `supabase status -o env`, crea/actualiza el usuario de Auth
y siembra únicamente las filas mínimas de `app_users` e
`institucion_miembros`. No imprime tokens ni claves.

Uso:
    python -m eval.seed_local_synthetic \
      --env-file /ruta/al/proyecto-supabase/.env.local \
      --jwt-file /ruta/segura/local_test.jwt
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

INSTITUTION_NAME = "Institucion Sintetica Voxia"
INSTITUTION_CODE = "LOCAL-SYNTHETIC"
STUDENT_EMAIL = "estudiante.sintetico@example.test"
STUDENT_NAME = "Estudiante Sintetico"


def is_local_url(url: str) -> bool:
    """The seed must never touch a hosted Supabase project."""
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "127.0.0.1",
        "localhost",
        "::1",
    }


def _client(url: str, key: str):
    from supabase import create_client

    return create_client(url, key)


def _ensure_auth_user(admin, auth_client, password: str) -> str:
    try:
        response = auth_client.auth.sign_in_with_password(
            {"email": STUDENT_EMAIL, "password": password}
        )
    except Exception:
        response = None

    if response and response.user:
        return str(response.user.id)

    admin.auth.admin.create_user(
        {
            "email": STUDENT_EMAIL,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"full_name": STUDENT_NAME},
        }
    )
    response = auth_client.auth.sign_in_with_password(
        {"email": STUDENT_EMAIL, "password": password}
    )
    if not response.user or not response.session:
        raise RuntimeError("No se pudo iniciar sesión con el usuario sintético")
    return str(response.user.id)


def _ensure_institution(admin) -> int:
    existing = (
        admin.table("instituciones")
        .select("id")
        .eq("codigo", INSTITUTION_CODE)
        .limit(1)
        .execute()
    )
    if existing.data:
        return int(existing.data[0]["id"])
    created = (
        admin.table("instituciones")
        .insert(
            {
                "nombre": INSTITUTION_NAME,
                "codigo": INSTITUTION_CODE,
                "pais": "Paraguay",
                "activo": True,
            }
        )
        .execute()
    )
    return int(created.data[0]["id"])


def _ensure_app_user(admin, external_auth_id: str) -> None:
    existing = (
        admin.table("app_users")
        .select("id")
        .eq("external_auth_id", external_auth_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        return
    admin.table("app_users").insert(
        {
            "external_auth_id": external_auth_id,
            "email": STUDENT_EMAIL,
            "full_name": STUDENT_NAME,
            "role": "STUDENT",
            "is_active": True,
        }
    ).execute()


def _ensure_membership(admin, external_auth_id: str, institucion_id: int) -> None:
    existing = (
        admin.table("institucion_miembros")
        .select("id")
        .eq("external_auth_id", external_auth_id)
        .eq("activo", True)
        .limit(1)
        .execute()
    )
    if existing.data:
        return
    admin.table("institucion_miembros").insert(
        {
            "institucion_id": institucion_id,
            "external_auth_id": external_auth_id,
            "tipo_miembro": "ESTUDIANTE",
            "activo": True,
        }
    ).execute()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--jwt-file", required=True)
    parser.add_argument(
        "--password",
        default=os.environ.get("LOCAL_SYNTHETIC_PASSWORD", "LocalSyntheticOnly-2026!"),
    )
    args = parser.parse_args()

    values = dotenv_values(args.env_file)
    url = values.get("API_URL")
    service_key = values.get("SERVICE_ROLE_KEY")
    anon_key = values.get("ANON_KEY")
    if not url or not service_key or not anon_key:
        print("Faltan API_URL, SERVICE_ROLE_KEY o ANON_KEY en el env-file")
        return 2

    if not is_local_url(url):
        print("Este seed solo acepta un Supabase local (127.0.0.1/localhost)")
        return 2

    auth_client = _client(url, anon_key)
    admin = _client(url, service_key)
    external_auth_id = _ensure_auth_user(admin, auth_client, args.password)
    institucion_id = _ensure_institution(admin)
    _ensure_app_user(admin, external_auth_id)
    _ensure_membership(admin, external_auth_id, institucion_id)

    signed = auth_client.auth.sign_in_with_password(
        {"email": STUDENT_EMAIL, "password": args.password}
    )
    if not signed.session:
        print("No se pudo obtener el JWT local")
        return 2

    jwt_path = Path(args.jwt_file)
    jwt_path.parent.mkdir(parents=True, exist_ok=True)
    jwt_path.write_text(signed.session.access_token, encoding="utf-8")
    os.chmod(jwt_path, 0o600)

    print("Usuario sintético listo.")
    print(f"institucion_id={institucion_id}")
    print(f"external_auth_id={external_auth_id}")
    print(f"jwt_file={jwt_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
