from __future__ import annotations

import eval.run_eval as run_eval
from eval.load_local import _percentile
from eval.pii_smoke import CASOS, _generated_negative_controls, _generated_synthetic_cases
from eval.run_eval import _fuente_encontrada
from eval import gen_wer_audios as wer_audio_generator
from eval.seed_local_synthetic import is_local_url
from eval.wer import wer
from eval.wer import main as run_wer


def test_source_match_requires_complete_normalized_expected_title() -> None:
    result = {"sources": [{"document": "Reglamento Académico Institucional"}]}

    assert _fuente_encontrada(result, "Reglamento Academico") is True
    assert _fuente_encontrada(result, "Reglamento de Matrícula") is False


def test_source_match_does_not_accept_only_a_shared_generic_word() -> None:
    result = {"sources": [{"document": "Reglamento de Becas"}]}

    assert _fuente_encontrada(result, "Reglamento de Matrícula") is False


def test_percentile_uses_nearest_rank_and_handles_empty_input() -> None:
    assert _percentile([], 95) is None
    assert _percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.0
    assert _percentile([1.0, 2.0, 3.0, 4.0], 95) == 4.0


def test_wer_normalizes_case_accents_and_punctuation() -> None:
    assert wer("¿Cómo estás, matrícula?", "como estas matricula") == 0.0


def test_wer_counts_word_substitution_and_insertion() -> None:
    assert wer("matricula vigente", "matricula nueva vigente") == 0.5


def test_pii_smoke_has_100_positive_cases_and_negative_controls() -> None:
    generated = _generated_synthetic_cases()
    controls = _generated_negative_controls()
    positive = [case for case in CASOS if case["id"] != "PII-05"] + generated
    negative = [case for case in CASOS if case["id"] == "PII-05"] + controls
    cases = positive + negative

    assert len(positive) == 100
    assert len(negative) == 20
    assert len(cases) == 120
    assert len({case["id"] for case in cases}) == 120
    assert all("ejemplo-test.edu" in case["texto"] for case in generated)


def test_run_eval_requires_explicit_external_provider_approval(monkeypatch) -> None:
    monkeypatch.setattr(run_eval, "EXTERNAL_PROVIDERS_APPROVED", False)

    assert run_eval.main() == 2


def test_local_seed_refuses_hosted_supabase_urls() -> None:
    assert is_local_url("http://127.0.0.1:54321") is True
    assert is_local_url("http://localhost:54321") is True
    assert is_local_url("https://project.supabase.co") is False
    assert is_local_url("http://127.0.0.1.evil.example") is False


def test_external_wer_tools_require_explicit_provider_approval(monkeypatch) -> None:
    monkeypatch.delenv("EVAL_EXTERNAL_PROVIDERS_APPROVED", raising=False)

    assert wer_audio_generator.main() == 2
    assert run_wer() == 2


def test_wer_audio_generator_refuses_to_overwrite_existing_output(monkeypatch, tmp_path) -> None:
    output_dir = tmp_path / "existing-run"
    output_dir.mkdir()
    (output_dir / "keep.txt").write_text("do not overwrite", encoding="utf-8")
    monkeypatch.setenv("EVAL_EXTERNAL_PROVIDERS_APPROVED", "true")
    monkeypatch.setattr(wer_audio_generator, "AUDIOS", output_dir)

    assert wer_audio_generator.main() == 2
    assert (output_dir / "keep.txt").read_text(encoding="utf-8") == "do not overwrite"
