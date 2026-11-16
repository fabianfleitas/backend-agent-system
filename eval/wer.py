#!/usr/bin/env python3
"""Cálculo de WER (Word Error Rate) del reconocimiento STT.

Para cada audio del directorio de evaluación (con su transcripción de referencia
`.txt`), transcribe con el servicio STT configurado y compara. Esto hace una
llamada externa directa, no pasa por el endpoint autenticado `/api/chat/voice`.

Uso:
    EVAL_EXTERNAL_PROVIDERS_APPROVED=true EVAL_WER_AUDIO_DIR=eval/audios/<run> python3 -m eval.wer

Requiere aprobación explícita de llamadas externas; la aprobación del operador
no reemplaza el consentimiento de participantes cuyos audios se hayan grabado.
"""

from __future__ import annotations

import os
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent
_audio_dir = Path(os.environ.get("EVAL_WER_AUDIO_DIR", str(ROOT / "audios")))
AUDIOS = _audio_dir if _audio_dir.is_absolute() else (Path.cwd() / _audio_dir).resolve()
REPORTS = ROOT / "reports"


def _external_provider_approved() -> bool:
    return os.environ.get("EVAL_EXTERNAL_PROVIDERS_APPROVED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _normalize_words(text: str) -> List[str]:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.findall(r"[a-z0-9]+", without_marks)


def edit_distance(reference: str, hypothesis: str) -> tuple[int, int]:
    ref = _normalize_words(reference)
    hyp = _normalize_words(hypothesis)
    n = len(ref)
    if n == 0:
        return len(hyp), 0
    previous = list(range(len(hyp) + 1))
    for i, ref_word in enumerate(ref, start=1):
        current = [i]
        for j, hyp_word in enumerate(hyp, start=1):
            if ref_word == hyp_word:
                current.append(previous[j - 1])
            else:
                current.append(1 + min(previous[j], current[j - 1], previous[j - 1]))
        previous = current
    return previous[-1], n


def wer(reference: str, hypothesis: str) -> float:
    distance, reference_words = edit_distance(reference, hypothesis)
    return distance / reference_words if reference_words else 0.0


def _transcribe_file(audio_path: Path, content_type: str) -> str:
    from app.services.transcription_service import TranscriptionService

    stt = TranscriptionService().transcribe(
        audio_path.read_bytes(),
        audio_path.name,
        content_type,
    )
    if not stt.ok:
        raise RuntimeError(f"STT falló: {stt.error}")
    return stt.text


def main() -> int:
    if not _external_provider_approved():
        print(
            "Se requiere EVAL_EXTERNAL_PROVIDERS_APPROVED=true para autorizar "
            "llamadas externas de STT durante esta evaluación."
        )
        return 2
    if not AUDIOS.exists():
        print("No existe el directorio de audios indicado (agregar pares de audio y referencia .txt).")
        return 1
    from app.core.config import settings

    results: List[Dict] = []
    total_wer = 0.0
    total_edit_distance = 0
    total_reference_words = 0
    count = 0
    for audio in sorted(AUDIOS.glob("*.wav")) + sorted(AUDIOS.glob("*.mp3")):
        ref_file = audio.with_suffix(".txt")
        if not ref_file.exists():
            continue
        reference = ref_file.read_text(encoding="utf-8").strip()
        content_type = "audio/wav" if audio.suffix == ".wav" else "audio/mpeg"
        hypothesis = _transcribe_file(audio, content_type)
        distance, reference_words = edit_distance(reference, hypothesis)
        value = distance / reference_words if reference_words else 0.0
        total_wer += value
        total_edit_distance += distance
        total_reference_words += reference_words
        count += 1
        results.append(
            {
                "audio": audio.name,
                "reference_words": reference_words,
                "edit_distance": distance,
                "wer": round(value, 4),
                "reference": reference,
                "hypothesis": hypothesis,
            }
        )

    if count == 0:
        print("No se encontraron pares audio + .txt de referencia en eval/audios/.")
        return 1
    macro_wer = total_wer / count
    corpus_wer = total_edit_distance / total_reference_words if total_reference_words else 0.0
    print(f"WER macro: {macro_wer:.2%} | WER corpus: {corpus_wer:.2%} sobre {count} audios")
    for r in results:
        print(f"  {r['audio']}: {r['wer']:.2%}")
    REPORTS.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS / f"wer_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    report_path.write_text(
        json.dumps(
            {
                "fecha": datetime.now(timezone.utc).isoformat(),
                "audio_dir": str(AUDIOS),
                "audios_evaluados": count,
                "audio_manifest": (
                    json.loads((AUDIOS / "manifest.json").read_text(encoding="utf-8"))
                    if (AUDIOS / "manifest.json").exists()
                    else None
                ),
                "provider_gateway": "OpenRouter",
                "stt_model": settings.stt_model,
                "external_provider_approval": True,
                "macro_wer": round(macro_wer, 4),
                "corpus_wer": round(corpus_wer, 4),
                "total_edit_distance": total_edit_distance,
                "total_reference_words": total_reference_words,
                "items": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Reporte: {report_path}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
