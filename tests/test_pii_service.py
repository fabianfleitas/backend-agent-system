from __future__ import annotations

"""Tests unitarios del pipeline PII (§16): tokenización, merge de detecciones,
formats locales, self-PII (perfil) y fail-closed sin Presidio/spaCy instalados.

Se usan fakes (detector disponible/no disponible, repo en memoria) para no
depender de presidio-analyzer ni del modelo spaCy. Ejecuta:
    python3 -m pytest tests/test_pii_service.py
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.services.pii_service import (
    PiiService,
    _apply_tokens,
    _merge_detections,
)


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
    result = service.anonymize("Cédula 12345678.")
    assert result.available is False
    assert result.text == "Cédula 12345678."
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
