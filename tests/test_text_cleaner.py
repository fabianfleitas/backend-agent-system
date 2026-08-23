from __future__ import annotations

from app.services.text_cleaner import clean_page_text, normalize_for_dedup


def test_collapses_duplicate_spaces() -> None:
    assert clean_page_text("Hola     mundo") == "Hola mundo"


def test_collapses_tabs() -> None:
    assert clean_page_text("a\t\tb") == "a b"


def test_normalizes_newlines() -> None:
    assert clean_page_text("linea1\r\nlinea2") == "linea1\nlinea2"
    assert clean_page_text("a\rb") == "a\nb"


def test_collapses_excess_newlines() -> None:
    assert clean_page_text("a\n\n\n\nb") == "a\n\nb"


def test_removes_zero_width_and_form_feed() -> None:
    text = "a\u200bb\u200cc\u200dd\ufeffe\x0cf"
    assert clean_page_text(text) == "abcdef"
    assert "\x0c" not in clean_page_text("a\x0cb")
    assert "\u200b" not in clean_page_text("a\u200bb")


def test_nfkc_ligatures() -> None:
    assert clean_page_text("\ufb01") == "fi"
    assert clean_page_text("\ufb02") == "fl"


def test_nfkc_smart_quotes() -> None:
    result = clean_page_text("\u201cHola\u201d")
    assert "\u201c" not in result
    assert "\u201d" not in result


def test_preserves_article_marker() -> None:
    assert "Artículo 1" in clean_page_text("El texto dice Artículo 1 y sigue")


def test_preserves_list_markers() -> None:
    text = "1.\na)\nII.\n- item\n$ 50\n25%"
    cleaned = clean_page_text(text)
    assert "1." in cleaned
    assert "a)" in cleaned
    assert "II." in cleaned
    assert "$ 50" in cleaned
    assert "25%" in cleaned


def test_preserves_dates_and_numbers() -> None:
    text = "Fecha: 17/08/2026, monto 1.234.567 pesos"
    cleaned = clean_page_text(text)
    assert "17/08/2026" in cleaned
    assert "1.234.567" in cleaned


def test_strips_edges() -> None:
    assert clean_page_text("   contenido   ") == "contenido"


def test_empty_input() -> None:
    assert clean_page_text("") == ""
    assert clean_page_text(None) == ""


def test_normalize_for_dedup_is_whitespace_insensitive() -> None:
    a = normalize_for_dedup("Artículo 1\n\nReglamento")
    b = normalize_for_dedup("articulo1Reglamento")
    assert a == b == "articulo1reglamento"


def test_normalize_for_dedup_ignores_accents_and_case() -> None:
    assert normalize_for_dedup("ÁRTÍCULO") == "articulo"