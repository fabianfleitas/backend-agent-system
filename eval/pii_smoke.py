#!/usr/bin/env python3
"""Prueba de humo RF-02: anonimizacion real con Presidio + formatos locales.

Ejecuta el detector real (spaCy es_core_news_md + regex de cedula UY/PY y telefono)
sobre un conjunto de textos ficticios y comprueba:
  1. que se detecten datos personales,
  2. que el texto enviado al proveedor no contenga los valores originales,
  3. que la desanonimizacion local (restore) recupere el texto original.

No realiza llamadas a servicios externos.

Uso:
    python3 -m eval.pii_smoke
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
VERBOSE = os.environ.get("EVAL_PII_VERBOSE", "false").lower() in {"1", "true", "yes", "y", "on"}

# Textos 100% ficticios. No contienen datos de personas reales.
#
# `debe_anonimizar` lista los valores que, por ser datos personales, tienen que
# llegar tokenizados al proveedor. Se evalua independientemente de si el detector
# los reconoce: si un valor de esta lista sobrevive en el texto anonimizado, es
# una fuga, y el caso se marca como FALLA aunque `detected_count` sea > 0.
CASOS = [
    {
        "id": "PII-01",
        "tipo": "CedulaCi (uruguaya)",
        "texto": "Soy Claudia Fernandez. Mi cedula es 1.234.567-8. ¿Quais son los requisitos de matricula?",
        "perfil": {"full_name": "Claudia Fernandez", "email": "claudia.fernandez@ejemplo-test.edu"},
        "debe_anonimizar": ["1.234.567-8"],
    },
    {
        "id": "PII-02",
        "tipo": "CedulaCi (paraguaya, 6-9 digitos)",
        "texto": "Mi cedula es 12345678 y mi correo es jose.gomez@ejemplo-test.edu. ¿Cuando abren las inscripciones?",
        "perfil": {"full_name": "Jose Gomez", "email": "jose.gomez@ejemplo-test.edu"},
        "debe_anonimizar": ["12345678", "jose.gomez@ejemplo-test.edu"],
    },
    {
        "id": "PII-03",
        "tipo": "Telefono LATAM + nombre",
        "texto": "Soy Camila Ramos, mi telefono es +595 981 234 567. Necesito informacion sobre becas.",
        "perfil": {"full_name": "Camila Ramos", "email": "camila.ramos@ejemplo-test.edu"},
        "debe_anonimizar": ["+595 981 234 567"],
    },
    {
        "id": "PII-04",
        "tipo": "CedulaCi con puntos (paraguaya)",
        "texto": "Mi cedula es 12.345.678. ¿Cuanto es el costo de la matricula?",
        "perfil": {"full_name": "Carlos Diaz", "email": "carlos.diaz@ejemplo-test.edu"},
        "debe_anonimizar": ["12.345.678"],
    },
    {
        "id": "PII-05",
        "tipo": "Sin datos personales (control negativo)",
        "texto": "¿Quais son los horarios de las clases de theory?",
        "perfil": {"full_name": "Ana Torres", "email": "ana.torres@ejemplo-test.edu"},
        "debe_anonimizar": [],
    },
]


def _generated_synthetic_cases() -> list[dict]:
    """Create deterministic fictional variants without using real people's data."""
    cases: list[dict] = []
    first_names = ["Alma", "Bruno", "Carla", "Diego", "Elena", "Fabio"]
    last_names = ["Prueba", "Demo", "Sintetico", "Ficticio", "Ensayo"]

    def add_case(index: int, kind: str, identifier: str) -> None:
        full_name = f"{first_names[index % len(first_names)]} {last_names[index % len(last_names)]}{index:03d}"
        email = f"persona{index:03d}@ejemplo-test.edu"
        if kind == "telefono y correo":
            personal_value = f"+595 981 000 {index:03d}"
            personal_label = "telefono"
        else:
            personal_value = identifier
            personal_label = "cedula"
        text = (
            f"Soy {full_name}. Mi {personal_label} es {personal_value} y mi correo es {email}. "
            "Necesito información sobre matrícula."
        )
        cases.append(
            {
                "id": f"PII-SYN-{index:03d}",
                "tipo": kind,
                "texto": text,
                "perfil": {"full_name": full_name, "email": email},
                "debe_anonimizar": [personal_value, full_name, email],
            }
        )

    index = 1
    for i in range(24):
        add_case(index, "cedula paraguaya sin separadores", str(10_000_000 + i))
        index += 1
    for i in range(24):
        add_case(index, "cedula paraguaya con puntos", f"10.{i:03d}.{100 + i:03d}")
        index += 1
    for i in range(24):
        add_case(index, "cedula uruguaya", f"1.{234 + i:03d}.{500 + i:03d}-{i % 10}")
        index += 1
    for i in range(24):
        add_case(index, "telefono y correo", "")
        index += 1
    return cases


def _generated_negative_controls() -> list[dict]:
    """Natural academic queries without PII to measure detector false positives."""
    prompts = [
        "Necesito consultar el calendario académico y las fechas de examen.",
        "¿Qué documentos necesito para la matrícula?",
        "¿Cuándo comienza el próximo semestre académico?",
        "¿Dónde puedo consultar el calendario de exámenes?",
        "¿Qué requisitos tiene el trámite de reingreso?",
        "¿Cómo se solicita una beca por mérito académico?",
        "¿Cuál es el horario de atención de la biblioteca?",
        "¿Qué pasos debo seguir para pedir un certificado de estudios?",
        "¿Cómo consulto las materias disponibles para el próximo periodo?",
        "¿Qué reglamento establece las normas de convivencia?",
        "¿Dónde se publican las fechas de inscripción?",
        "¿Cómo funciona el régimen de correlatividades?",
        "¿Qué opciones de pago ofrece la institución?",
        "¿Cuándo se publican las calificaciones finales?",
        "¿Qué procedimiento se sigue para solicitar una equivalencia?",
        "¿Cómo ingreso al campus virtual?",
        "¿Qué requisitos se exigen para presentar el trabajo final?",
        "¿En qué fechas se realizan los exámenes parciales?",
        "Necesito información sobre aranceles académicos.",
    ]
    return [
        {
            "id": f"PII-NEG-{index:03d}",
            "tipo": "Control negativo sin datos personales",
            "texto": prompt,
            "perfil": {},
            "debe_anonimizar": [],
        }
        for index, prompt in enumerate(prompts, start=1)
    ]


def main() -> int:
    from app.services.pii_service import PiiService

    service = PiiService()
    print("=" * 78)
    print("PRUEBA DE HUMO RF-02 - ANONIMIZACION DE DATOS SENSIBLES (motor real)")
    print("=" * 78)
    print(f"Fecha              : {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Detector disponible: {service.available}")
    if not service.available:
        print(f"ERROR             : {service.detector.error if service.detector else 'sin detector'}")
        print("Instale: python3 -m pip install presidio-analyzer && python3 -m spacy download es_core_news_md")
        return 2
    print("Motor              : Presidio NER (spaCy) + formatos locales (cedula UY/PY, telefono)")
    print()

    generated_positive = _generated_synthetic_cases()
    negative_controls = _generated_negative_controls()
    casos = CASOS + generated_positive + negative_controls
    filas = []
    todo_ok = True
    expected_values_total = 0
    expected_values_masked = 0
    for caso in casos:
        original = caso["texto"]
        resultado = service.anonymize(original, user_profile=caso["perfil"])

        # Valores originalmente detectados que NO deben viajar al proveedor.
        valores = {m["original_value"] for m in resultado.mappings}
        fugas = [v for v in valores if v and v in resultado.text]

        # Valores que DEBIAN estar tokenizados por ser datos personales, se detecten
        # o no. Esta comprobacion es la que detecta falsos negativos del detector.
        expected_values = list(dict.fromkeys(caso["debe_anonimizar"]))
        # Los datos de perfil solo cuentan si aparecen en la consulta original.
        expected_values.extend(
            v for v in (caso["perfil"].get("full_name"), caso["perfil"].get("email"))
            if v and v.lower() in original.lower() and v not in expected_values
        )
        expected_values_total += len(expected_values)
        fuga_perfil = [v for v in expected_values if v.lower() in resultado.text.lower()]
        expected_values_masked += len(expected_values) - len(fuga_perfil)
        fugas_esperadas = [v for v in caso["debe_anonimizar"] if v and v.lower() in resultado.text.lower()]
        unexpected_detections = [
            m["original_value"]
            for m in resultado.mappings
            if not any(
                expected.lower() in m["original_value"].lower()
                or m["original_value"].lower() in expected.lower()
                for expected in expected_values
            )
        ]

        restaurado = service.restore(resultado.text, resultado.mappings)
        roundtrip_ok = restaurado == original

        es_control = caso["id"] == "PII-05" or caso["id"].startswith("PII-NEG-")
        if es_control:
            ok = resultado.detected_count == 0
        else:
            ok = (
                resultado.detected_count > 0
                and not fugas
                and not fugas_esperadas
                and not fuga_perfil
                and roundtrip_ok
            )
        todo_ok = todo_ok and ok

        if VERBOSE:
            print(f"--- {caso['id']} | {caso['tipo']} ---")
            print(f"  ORIGINAL      : {original}")
            print(f"  ANONIMIZADO  : {resultado.text}")
            print(f"  DETECTADOS    : {resultado.detected_count}")
            for m in resultado.mappings:
                print(f"      {m['token']:<22} <- {m['original_value']}")
            if fugas or fuga_perfil:
                print(f"  FUGA AL PROVEEDOR : SI -> {fugas + fuga_perfil}")
            else:
                print("  FUGA AL PROVEEDOR : NO")
            if fugas_esperadas:
                print(f"  NO DETECTADO (FUGA): SI -> {fugas_esperadas}")
                print("      ^ falso negativo del detector: dato personal sin anonimizar")
            else:
                print("  NO DETECTADO (FUGA): NO")
            if unexpected_detections:
                print(f"  FALSOS POSITIVOS : {unexpected_detections}")
            print(f"  RESTAURADO   : {restaurado}")
            print(f"  ROUND-TRIP OK: {'SI' if roundtrip_ok else 'NO'}")
            print(f"  RESULTADO     : {'OK' if ok else 'FALLA'}")
            print()

        filas.append({
            "id": caso["id"],
            "tipo": caso["tipo"],
            "original": original,
            "anonimizado": resultado.text,
            "detectados": resultado.detected_count,
            "mappings": resultado.mappings,
            "detecciones_no_esperadas": unexpected_detections,
            "valores_esperados": len(expected_values),
            "valores_esperados_anonimizados": len(expected_values) - len(fuga_perfil),
            "fuga_al_proveedor": bool(fugas or fuga_perfil),
            "no_detectado": fugas_esperadas,
            "roundtrip_ok": roundtrip_ok,
            "resultado": "OK" if ok else "FALLA",
        })

    resumen = {
        "fecha": datetime.now(timezone.utc).isoformat(),
        "detector_disponible": service.available,
        "total_casos": len(filas),
        "casos_positivos": sum(
            1 for f in filas if not f["id"].startswith("PII-NEG-") and f["id"] != "PII-05"
        ),
        "controles_negativos": sum(
            1 for f in filas if f["id"].startswith("PII-NEG-") or f["id"] == "PII-05"
        ),
        "casos_ok": sum(1 for f in filas if f["resultado"] == "OK"),
        "casos_falla": sum(1 for f in filas if f["resultado"] != "OK"),
        "valores_personales_esperados": expected_values_total,
        "valores_personales_anonimizados": expected_values_masked,
        "cobertura_anonimizacion": (
            round(expected_values_masked / expected_values_total, 4)
            if expected_values_total
            else None
        ),
        "total_detecciones": sum(f["detectados"] for f in filas),
        "detecciones_no_esperadas": sum(len(f["detecciones_no_esperadas"]) for f in filas),
        "precision_detecciones_estimada": (
            round(
                expected_values_masked / sum(f["detectados"] for f in filas),
                4,
            )
            if sum(f["detectados"] for f in filas)
            else None
        ),
        "controles_negativos_con_detecciones": sum(
            1
            for f in filas
            if (f["id"] == "PII-05" or f["id"].startswith("PII-NEG-"))
            and f["detectados"] > 0
        ),
        "valores_no_esperados": sorted(
            {v for f in filas for v in f["detecciones_no_esperadas"]}
        ),
        "fugas_detectadas": sum(1 for f in filas if f["fuga_al_proveedor"]),
        "valores_no_detectados": sorted(
            {v for f in filas for v in f["no_detectado"]}
        ),
        "casos": filas,
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"pii_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    out.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 78)
    print(
        f"Casos: {resumen['casos_ok']}/{resumen['total_casos']} OK "
        f"({resumen['casos_positivos']} positivos, {resumen['controles_negativos']} controles) | "
        f"PII cubiertos: {resumen['valores_personales_anonimizados']}/"
        f"{resumen['valores_personales_esperados']} | "
        f"detecciones: {resumen['total_detecciones']} | "
        f"no esperadas: {resumen['detecciones_no_esperadas']} | "
        f"controles negativos con detecciones: {resumen['controles_negativos_con_detecciones']} | "
        f"fugas: {resumen['fugas_detectadas']}"
    )
    if resumen["valores_no_detectados"]:
        print("Valores personales que quedaron sin anonimizar (falsos negativos):")
        for v in resumen["valores_no_detectados"]:
            print(f"  - {v}")
    if resumen["valores_no_esperados"]:
        print("Valores detectados que no estaban etiquetados como PII:")
        for v in resumen["valores_no_esperados"]:
            print(f"  - {v}")
    print(f"Reporte: {out}")
    if not todo_ok:
        global_result = "NO CUMPLIDO"
    elif resumen["detecciones_no_esperadas"]:
        global_result = "COBERTURA Y CERO FUGAS CUMPLIDAS; REVISAR FALSOS POSITIVOS"
    else:
        global_result = "CUMPLIDO"
    print("RESULTADO GLOBAL:", global_result)
    return 0 if todo_ok else 1


if __name__ == "__main__":
    sys.exit(main())
