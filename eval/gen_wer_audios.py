#!/usr/bin/env python3
"""Genera audios sintéticos limpios de referencia para el WER (RF-07).

Sintetiza hasta 20 frases sin datos personales del Gold Dataset y las guarda en
un directorio único con referencias y manifest. No representa voz humana en
condiciones reales. Requiere autorización explícita para llamadas TTS externas.

Uso:
    python3 -m eval.gen_wer_audios
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = ROOT / "audios" / f"extended_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
AUDIOS = Path(os.environ.get("EVAL_WER_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)))
DATASET = ROOT / "gold_dataset.json"
COUNT = int(os.environ.get("EVAL_WER_AUDIO_COUNT", "20"))
MAX_COUNT = 20


def _external_provider_approved() -> bool:
    return os.environ.get("EVAL_EXTERNAL_PROVIDERS_APPROVED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _speakable(text: str) -> str:
    # Preserve Spanish diacritics so the audio and reference transcript describe
    # the same utterance. WER normalization is handled by eval.wer.
    return " ".join(text.split())


def main() -> int:
    if not _external_provider_approved():
        print(
            "Se requiere EVAL_EXTERNAL_PROVIDERS_APPROVED=true para autorizar "
            "llamadas externas de TTS durante esta evaluación."
        )
        return 2
    if COUNT < 1 or COUNT > MAX_COUNT:
        print(f"EVAL_WER_AUDIO_COUNT debe estar entre 1 y {MAX_COUNT}")
        return 2
    if AUDIOS.exists() and any(AUDIOS.iterdir()):
        print(f"El directorio de salida ya contiene archivos; se rechaza sobrescribir: {AUDIOS}")
        return 2

    from app.core.config import settings
    from app.services.synthesis_service import SynthesisService

    data = json.loads(DATASET.read_text(encoding="utf-8"))
    items = data["items"][:COUNT]
    if len(items) < COUNT:
        print(f"Aviso: el Gold Dataset solo contiene {len(items)} consultas; se generará esa cantidad.")
    AUDIOS.mkdir(parents=True, exist_ok=True)
    synth = SynthesisService()
    created = 0
    for idx, item in enumerate(items, start=1):
        text = _speakable(item["pregunta"])
        result = synth.synthesize(text)
        if not result.ok:
            print(f"ERROR synth {item['id']}: {result.error}")
            continue
        audio = AUDIOS / f"gold_{idx:03d}.mp3"
        audio.write_bytes(result.audio_bytes)
        (AUDIOS / f"gold_{idx:03d}.txt").write_text(text, encoding="utf-8")
        created += 1
        print(f"OK g{idx:02d} -> {audio.name} ({len(result.audio_bytes)} bytes)")
    manifest = {
        "fecha": datetime.now(timezone.utc).isoformat(),
        "audio_count_requested": COUNT,
        "audio_count_created": created,
        "source_dataset": DATASET.name,
        "audio_condition": "TTS sintético limpio; no representa voz humana en ruido ambiente",
        "provider_gateway": "OpenRouter",
        "tts_model": settings.tts_model,
        "external_provider_approval": True,
    }
    (AUDIOS / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nAudios generados: {created}/{COUNT} en {AUDIOS}")
    print("Ahora ejecuta: EVAL_EXTERNAL_PROVIDERS_APPROVED=true python3 -m eval.wer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
