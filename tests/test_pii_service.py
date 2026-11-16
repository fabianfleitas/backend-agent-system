from __future__ import annotations

"""Tests unitarios del pipeline PII (§16): tokenización, merge de detecciones,
formats locales, self-PII (perfil) y fail-closed sin Presidio/spaCy instalados.

Se usan fakes (detector disponible/no disponible, repo en memoria) para no
depender de presidio-analyzer ni del modelo spaCy. Ejecuta:
    python3 -m pytest tests/test_pii_service.py
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import List, Optional

from app.services.pii_service import (
    PiiService,
    PresidioPiiDetector,
    _analyze_local_formats,
    _apply_tokens,
    _merge_detections,
)


def test_presidio_filters_only_known_span_specific_location_false_positive() -> None:
    text = "Necesito información sobre matrícula. Claudia confirma el trámite."

    class FakeEngine:
        def analyze(self, text: str, language: str):
            return [
                SimpleNamespace(start=0, end=9, entity_type="LOCATION"),
                SimpleNamespace(
                    start=text.index("Claudia"),
                    end=text.index("Claudia") + len("Claudia"),
                    entity_type="PERSON",
                ),
            ]

    detector = PresidioPiiDetector.__new__(PresidioPiiDetector)
    detector._engine = FakeEngine()
    detector.available = True
    detector.language = "es"

    results = detector.analyze(text)

    assert results == [
        {
            "start": text.index("Claudia"),
            "end": text.index("Claudia") + len("Claudia"),
            "pii_type": "PERSON",
        }
    ]


def test_presidio_does_not_filter_other_entity_types_or_other_languages() -> None:
    text = "Necesito"

    class FakeEngine:
        def analyze(self, text: str, language: str):
            entity_type = "EMAIL_ADDRESS" if language == "es" else "PERSON"
            return [SimpleNamespace(start=0, end=len(text), entity_type=entity_type)]

    detector = PresidioPiiDetector.__new__(PresidioPiiDetector)
    detector._engine = FakeEngine()
    detector.available = True
    detector.language = "es"

    assert detector.analyze(text) == [{"start": 0, "end": 8, "pii_type": "EMAIL_ADDRESS"}]
    assert detector.analyze(text, language="en") == [
        {"start": 0, "end": 8, "pii_type": "PERSON"}
    ]


def _detec(text: str, pii_type: str, start: int, end: Optional[int] = None) -> dict:
    return {"text": text, "pii_type": pii_type, "start": start, "end": end or start + len(text)}


def test_apply_tokens_reemplaza_con_tokens_secuenciales_por_tipo() -> None:
    text = "La cédula 12345678 y el correo ana@inst.edu son datos de Ana."
    detections = [
        _detec("12345678", "NUMERO_CEDULA", text.find("12345678")),
        _detec("ana@inst.edu", "EMAIL_ADDRESS", text.find("ana@inst.edu")),
    ]
    anonymized, mappings = _apply_tokens(text, detections)
    assert "12345678" not in anonymized
    assert "ana@inst.edu" not in anonymized
    assert anonymized.count("[PII_NUMERO_CEDULA_") == 1
    assert anonymized.count("[PII_EMAIL_ADDRESS_") == 1
    assert len(mappings) == 2
    assert mappings[0]["token"] == "[PII_NUMERO_CEDULA_1]"
    assert mappings[0]["pii_type"] == "NUMERO_CEDULA"
    assert mappings[0]["original_value"] == "12345678"
    assert mappings[1]["token"] == "[PII_EMAIL_ADDRESS_2]"
    assert mappings[1]["original_value"] == "ana@inst.edu"


def test_merge_detections_descarta_solapes_menores() -> None:
    detections = [
        _detec("Ana María García", "PERSON", 0, 16),
        _detec("Ana María", "PERSON", 0, 8),
    ]
    merged = _merge_detections(detections)
    assert len(merged) == 1
    assert merged[0]["start"] == 0
    assert merged[0]["end"] == 16


def test_local_formats_detecta_cedula_paraguaya() -> None:
    # Formato con puntos y plano (6–9 dígitos, sin dígito verificador)
    for value in ("1.234.567", "12.345.678", "1234567", "12345678"):
        text = f"Mi cédula es {value}."
        detections = _analyze_local_formats(text)
        assert len(detections) == 1, value
        assert detections[0]["pii_type"] == "CI"
        assert detections[0]["start"] == text.find(value)
        assert detections[0]["end"] == text.find(value) + len(value)


def test_local_formats_sigue_detectando_cedula_uruguaya() -> None:
    for value in ("1.234.567-8", "1234567-8"):
        detections = _analyze_local_formats(f"Cédula {value}.")
        assert detections, value
        assert detections[0]["pii_type"] == "CI"


def test_local_formats_detecta_telefono_con_espacios() -> None:
    # Regresión: el formato agrupado 3-3-3 con espacios no era detectado por la
    # regex anterior (exigía grupos de 4–8 dígitos consecutivos).
    text = "Soy Camila Ramos, mi telefono es +595 981 234 567. Necesito informacion."
    detections = _analyze_local_formats(text)
    phones = [d for d in detections if d["pii_type"] == "PHONE_NUMBER"]
    assert len(phones) == 1
    value = "+595 981 234 567"
    assert phones[0]["start"] == text.find(value)
    assert phones[0]["end"] == text.find(value) + len(value)


def test_local_formats_detecta_telefonos_formatos_variados() -> None:
    # 2-3-3, con guiones, sin separadores y con prefijo de un dígito.
    for value in ("+598 99 123 456", "+595-981-234-567", "+595981234567", "+1 202 555 0147"):
        detections = [d for d in _analyze_local_formats(f"Tel {value}.") if d["pii_type"] == "PHONE_NUMBER"]
        assert detections, value
        assert detections[0]["end"] - detections[0]["start"] == len(value)


def test_local_formats_no_confunde_cedula_con_telefono() -> None:
    # Control negativo: una cédula sin prefijo internacional no debe clasificarse
    # como teléfono.
    detections = _analyze_local_formats("Mi cédula es 12.345.678.")
    assert all(d["pii_type"] != "PHONE_NUMBER" for d in detections)
    assert any(d["pii_type"] == "CI" for d in detections)


def test_local_formats_detecta_correo_electronico() -> None:
    # Regresión: el reconocedor NER a veces clasifica el correo como PERSON/LOCATION
    # o lo omite; el patrón local debe tokenizarlo como EMAIL_ADDRESS.
    for value in ("claudia.fernandez@ejemplo-test.edu", "jose.gomez@empresa.com.py", "a@b.io"):
        detections = [d for d in _analyze_local_formats(f"mi correo es {value}.") if d["pii_type"] == "EMAIL_ADDRESS"]
        assert detections, value
        assert detections[0]["end"] - detections[0]["start"] == len(value)


def test_restore_reemplaza_tokens_por_valores_originales() -> None:
    mappings = [
        {"token": "[PII_NUMERO_CEDULA_1]", "pii_type": "NUMERO_CEDULA", "original_value": "12345678"},
        {"token": "[PII_EMAIL_ADDRESS_2]", "pii_type": "EMAIL_ADDRESS", "original_value": "ana@inst.edu"},
    ]
    text = "El estudiante con [PII_NUMERO_CEDULA_1] y correo [PII_EMAIL_ADDRESS_2] fue atendido."
    restored = PiiService.restore(text, mappings)
    assert "12345678" in restored
    assert "ana@inst.edu" in restored
    assert "[PII_" not in restored


def test_restore_texto_vacio_o_sin_tokens() -> None:
    assert PiiService.restore("", [{"token": "[PII_CI_1]", "original_value": "x"}]) == ""
    assert PiiService.restore("respuesta sin tokens", []) == "respuesta sin tokens"
    assert PiiService.restore("respuesta sin tokens", [{"token": "[PII_CI_1]", "original_value": "x"}]) == "respuesta sin tokens"


class FakeDetector:
    def __init__(self, available: bool = True, error: Optional[str] = None) -> None:
        self.available = available
        self.error = error
        self.language = "es"

    def analyze(self, text: str, language: Optional[str] = None) -> List[dict]:
        detections: List[dict] = []
        for value, pii_type in (
            ("12345678", "NUMERO_CEDULA"),
            ("ana@inst.edu", "EMAIL_ADDRESS"),
        ):
            idx = text.find(value)
            if idx >= 0:
                detections.append(_detec(value, pii_type, idx, idx + len(value)))
        return detections


class FakePiiRepository:
    def __init__(self) -> None:
        self.rows: List[dict] = []

    def insert_mappings(self, rows: List[dict]) -> List[dict]:
        inserted: List[dict] = []
        for row in rows:
            record = dict(row)
            record["id"] = len(self.rows) + 1
            self.rows.append(record)
            inserted.append(record)
        return inserted


def _service(detector: FakeDetector, repo: Optional[FakePiiRepository] = None) -> PiiService:
    return PiiService(detector=detector, repository=repo or FakePiiRepository())  # type: ignore[arg-type]


def test_anonymize_con_detector_disponible_devuelve_mappings_y_tokens() -> None:
    service = _service(FakeDetector(available=True))
    result = service.anonymize("La cédula 12345678 y el correo ana@inst.edu de Ana.")
    assert result.available is True
    assert result.text.count("[PII_") == 2
    assert len(result.mappings) == 2
    assert result.mappings[0]["original_value"] == "12345678"
    assert result.mappings[0]["pii_type"] == "NUMERO_CEDULA"


def test_anonymize_fail_closed_sin_detector_no_llama_repo() -> None:
    repo = FakePiiRepository()
    service = _service(FakeDetector(available=False, error="modelo es_core_news_md no instalado"), repo)
    result = service.anonymize("Hola, necesito información sobre la matriculación.")
    assert result.available is False
    assert result.text == "Hola, necesito información sobre la matriculación."
    assert result.mappings == []
    assert result.error is not None
    assert service.persist_mappings([], audit_id="a1", external_auth_id="u1", institucion_id=None) == []
    assert repo.rows == []


def test_persist_mappings_inserta_rows_con_ttl_por_retention() -> None:
    repo = FakePiiRepository()
    service = _service(FakeDetector(available=True), repo)
    cutoff = datetime.now(timezone.utc) + timedelta(days=service.retention_days)
    rows = service.persist_mappings(
        [
            {"token": "[PII_NUMERO_CEDULA_1]", "pii_type": "NUMERO_CEDULA", "original_value": "12345678"},
            {"token": "[PII_EMAIL_ADDRESS_2]", "pii_type": "EMAIL_ADDRESS", "original_value": "ana@inst.edu"},
        ],
        audit_id="a1",
        external_auth_id="u1",
        institucion_id=7,
    )
    assert len(rows) == 2
    assert repo.rows[0]["token"] == "[PII_NUMERO_CEDULA_1]"
    assert repo.rows[0]["institucion_id"] == 7
    assert repo.rows[0]["external_auth_id"] == "u1"
    assert repo.rows[0]["audit_id"] == "a1"
    parsed = datetime.fromisoformat(repo.rows[0]["expires_at"])
    assert parsed >= cutoff - timedelta(seconds=5)
