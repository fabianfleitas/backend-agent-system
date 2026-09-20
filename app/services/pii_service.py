from __future__ import annotations

import logging
import re

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.repositories.pii_repository import PiiRepository

logger = logging.getLogger(__name__)


@dataclass
class AnonymizeResult:
    text: str
    mappings: List[dict] = field(default_factory=list)
    detected_count: int = 0
    available: bool = True
    error: Optional[str] = None


def _normalize_type(entity_type: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", entity_type or "UNKNOWN").strip("_")
    return cleaned.upper() or "UNKNOWN"


class PresidioPiiDetector:
    """Detector NER via Presidio (spaCy es). available=False si el modelo falta."""

    def __init__(self, model: Optional[str] = None, language: Optional[str] = None) -> None:
        self.model = model or settings.pii_nlp_model
        self.language = language or settings.pii_language
        self._engine: Any = None
        self.error: Optional[str] = None
        self.available = False
        self._load()

    def _load(self) -> None:
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider

            configuration = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": self.language, "model_name": self.model}],
            }
            provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = provider.create_engine()
            self._engine = AnalyzerEngine(nlp_engine=nlp_engine, default_score_threshold=0.5)
            self.available = True
        except Exception as exc:  # noqa: BLE001
            self.error = f"{type(exc).__name__}: {exc}"
            logger.warning("PII detector unavailable model=%s: %s", self.model, self.error)

    def analyze(self, text: str, language: Optional[str] = None) -> List[dict]:
        if not self._engine or not self.available:
            return []
        results = self._engine.analyze(text=text, language=language or self.language)
        return [
            {
                "start": int(r.start),
                "end": int(r.end),
                "pii_type": _normalize_type(r.entity_type),
            }
            for r in results
        ]


_presidio_detector: Optional[PresidioPiiDetector] = None


def get_presidio_detector() -> PresidioPiiDetector:
    global _presidio_detector
    if _presidio_detector is None:
        _presidio_detector = PresidioPiiDetector()
    return _presidio_detector


_LOCAL_PATTERNS: List[dict] = [
    # Cédula uruguaya: X.XXX.XXX-X / XXXXXXX-X
    {
        "pii_type": "CI",
        "regex": re.compile(r"\b\d{1,2}\.\d{3}\.\d{3}-[\dA-Z]\b|\b\d{6,7}-[\dA-Z]\b"),
    },
    # Teléfonos LATAM: +595 981 234 567 / +598 99 123 456
    {
        "pii_type": "PHONE_NUMBER",
        "regex": re.compile(r"\+\d{1,3}[\s\-]?\d{4,8}[\s\-]?\d{4,8}\b"),
    },
]


def _analyze_local_formats(text: str) -> List[dict]:
    detections: List[dict] = []
    for pattern in _LOCAL_PATTERNS:
        for match in pattern["regex"].finditer(text):
            detections.append(
                {"start": match.start(), "end": match.end(), "pii_type": pattern["pii_type"]}
            )
    return detections


def _analyze_self_pii(text: str, user_profile: Optional[dict]) -> List[dict]:
    detections: List[dict] = []
    if not user_profile:
        return detections
    email = user_profile.get("email")
    full_name = user_profile.get("full_name")
    if email:
        for match in re.finditer(re.escape(email), text, flags=re.IGNORECASE):
            detections.append(
                {"start": match.start(), "end": match.end(), "pii_type": "EMAIL_ADDRESS"}
            )
    if full_name:
        for match in re.finditer(re.escape(full_name), text):
            detections.append({"start": match.start(), "end": match.end(), "pii_type": "PERSON"})
    return detections


def _merge_detections(detections: List[dict]) -> List[dict]:
    """Elimina spans solapados conservando el primero (orden de aparición)."""
    ordered = sorted(detections, key=lambda d: (d["start"], -(d["end"] - d["start"])))
    merged: List[dict] = []
    last_end = -1
    for detection in ordered:
        if detection["start"] >= last_end:
            merged.append(detection)
            last_end = detection["end"]
    return merged


def _apply_tokens(text: str, detections: List[dict]) -> tuple[str, List[dict]]:
    if not detections:
        return text, []
    ordered = sorted(detections, key=lambda d: d["start"])
    # Tokens secuenciales globales por posición de aparición (determinista para
    # trazabilidad): [PII_NUMERO_CEDULA_1], [PII_EMAIL_ADDRESS_2], ...
    index_by_span: Dict[tuple[int, int], int] = {}
    for sequence, detection in enumerate(ordered, start=1):
        index_by_span[(detection["start"], detection["end"])] = sequence

    # Mappings en orden posicional (misma posición que en el texto original).
    mappings: List[dict] = []
    for detection in ordered:
        start, end = detection["start"], detection["end"]
        pii_type = detection["pii_type"]
        token = f"[PII_{pii_type}_{index_by_span[(start, end)]}]"
        mappings.append(
            {"token": token, "pii_type": pii_type, "original_value": text[start:end]}
        )

    # Reemplazo de atrás hacia adelante para no invalidar offsets previos: las
    # sustituciones más a la derecha no desplazan los índices de las de la
    # izquierda.
    result = text
    for detection in reversed(ordered):
        start, end = detection["start"], detection["end"]
        token = f"[PII_{detection['pii_type']}_{index_by_span[(start, end)]}]"
        result = result[:start] + token + result[end:]
    return result, mappings


class PiiService:
    def __init__(
        self,
        detector: Optional[PresidioPiiDetector] = None,
        repository: Optional[PiiRepository] = None,
        retention_days: Optional[int] = None,
    ) -> None:
        self.detector = detector or get_presidio_detector()
        self.repository = repository or PiiRepository()
        self.retention_days = (
            retention_days if retention_days is not None else settings.pii_mapping_retention_days
        )

    @property
    def available(self) -> bool:
        return bool(self.detector and self.detector.available)

    def anonymize(
        self,
        text: str,
        user_profile: Optional[dict] = None,
        language: Optional[str] = None,
    ) -> AnonymizeResult:
        if not text:
            return AnonymizeResult(text=text, available=self.available)

        available = self.available
        error: Optional[str] = None
        detections: List[dict] = []
        if available:
            try:
                detections = self.detector.analyze(text, language=language or settings.pii_language)
            except Exception as exc:  # noqa: BLE001
                available = False
                error = f"{type(exc).__name__}: {exc}"
                logger.error("PII detection failed: %s", error)
        else:
            error = getattr(self.detector, "error", None) or "presidio detector unavailable"

        detections = _merge_detections(
            detections + _analyze_self_pii(text, user_profile) + _analyze_local_formats(text)
        )
        anonymized, mappings = _apply_tokens(text, detections)
        return AnonymizeResult(
            text=anonymized,
            mappings=mappings,
            detected_count=len(mappings),
            available=available,
            error=error,
        )

    def persist_mappings(
        self,
        mappings: List[dict],
        audit_id: str,
        external_auth_id: str,
        institucion_id: Optional[int],
        expires_at: Optional[datetime] = None,
    ) -> List[dict]:
        if not mappings:
            return []
        cutoff = expires_at or datetime.now(timezone.utc) + timedelta(days=self.retention_days)
        rows = [
            {
                "audit_id": audit_id,
                "external_auth_id": external_auth_id,
                "token": m["token"],
                "pii_type": m["pii_type"],
                "original_value": m["original_value"],
                "institucion_id": institucion_id,
                "expires_at": cutoff.isoformat(),
            }
            for m in mappings
        ]
        try:
            return self.repository.insert_mappings(rows)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "PII mappings persist failed external_auth_id=%s error=%s",
                external_auth_id,
                exc,
            )
            return []