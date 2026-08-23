from __future__ import annotations

from app.services.chunking_service import (
    MIN_CHUNK_CHARS,
    PageText,
    chunk_pages,
)


def _page(page_number: int, text: str) -> PageText:
    return PageText(page_number=page_number, text=text)


def test_empty_document() -> None:
    result = chunk_pages([_page(1, ""), _page(2, "   ")])
    assert result.ok
    assert result.chunks == []
    assert result.total_chunks == 0


def test_recursive_split_without_structural_markers() -> None:
    body = ("El reglamento establece las normas generales de convivencia. " * 40) + (
        "Los estudiantes deben asistir puntualmente a clases. " * 40
    )
    result = chunk_pages([_page(1, body)])
    assert result.ok
    assert result.total_chunks >= 3
    for chunk in result.chunks:
        assert chunk.chunk_index == result.chunks.index(chunk)
        assert chunk.char_count > 0
        assert chunk.token_count > 0
    assert max(c.char_count for c in result.chunks) <= 1200 + 300
    assert result.total_chars >= len(body)


def test_overlap_between_consecutive_chunks() -> None:
    body = "Texto de régimen académico institucional. " * 120
    result = chunk_pages([_page(1, body)])
    assert result.total_chunks >= 2
    overlapping = any(chunk.text[-50:] in result.chunks[i + 1].text for i, chunk in enumerate(result.chunks[:-1]))
    assert overlapping


def test_structural_split_by_articulo() -> None:
    text = (
        "ORD/N° 1/26 - Preámbulo.\n\n"
        "ARTÍCULO 1.- El presente reglamento regula la matrícula.\n\n"
        "ARTÍCULO 2.- La matrícula se realiza en línea.\n\n"
        "Artículo 3.- Los plazos son improrrogables."
    )
    result = chunk_pages([_page(1, text)])
    assert result.ok
    joined = " ".join(c.text for c in result.chunks)
    assert "ARTÍCULO 1" in joined
    assert "ARTÍCULO 2" in joined
    assert "Artículo 3" in joined


def test_oversized_articulo_is_subsplit() -> None:
    long_article = "ARTÍCULO 7.- " + "La evaluación continua considera trabajos prácticos y exámenes parciales. " * 40
    result = chunk_pages([_page(1, long_article)])
    assert result.ok
    assert result.total_chunks >= 2
    texts = " ".join(c.text for c in result.chunks)
    assert "ARTÍCULO 7" in texts


def test_small_articulo_is_merged() -> None:
    text = (
        "ARTÍCULO 1.- El presente reglamento regula la vida académica de la institución "
        "y su aplicación es obligatoria para todos los estudiantes matriculados en "
        "cualquier programa de grado o posgrado del sistema.\n\n"
        "Artículo 2.- Corto."
    )
    result = chunk_pages([_page(1, text)])
    assert result.ok
    chunks_with_art2 = [c.text for c in result.chunks if "Artículo 2" in c.text]
    assert chunks_with_art2
    assert len(chunks_with_art2[0]) > MIN_CHUNK_CHARS


def test_duplicate_consecutive_pages_removed() -> None:
    body = "ARTÍCULO 1.- El reglamento académico establece normas generales."
    result = chunk_pages([_page(1, body), _page(2, body), _page(3, body)])
    assert result.dropped_duplicate_pages == 2
    assert result.ok
    assert result.total_chunks == 1


def test_page_number_tracking() -> None:
    pages = [
        _page(1, "TÍTULO I - Disposiciones generales.\n\nContenido de la primera página."),
        _page(
            2,
            "ARTÍCULO 5.- La asistencia a clases es obligatoria para todos los estudiantes "
            "inscriptos y su incumplimiento es sancionado conforme al reglamento interno.",
        ),
        _page(
            3,
            "ARTÍCULO 9.- Los exámenes parciales y finales son presenciales y se evalúan "
            "bajo los criterios establecidos por la facultad correspondiente.",
        ),
    ]
    result = chunk_pages(pages)
    assert result.ok
    by_text = {c.text[:20]: c.page_number for c in result.chunks}
    assert any("ARTÍCULO 5" in key for key in by_text if by_text[key] == 2)
    assert any("ARTÍCULO 9" in key for key in by_text if by_text[key] == 3)


def test_chunk_index_sequential_and_unique() -> None:
    text = (
        "ARTÍCULO 1.- Disposición general y alcance del reglamento institucional. "
        * 30
    )
    result = chunk_pages([_page(1, text)])
    indices = [c.chunk_index for c in result.chunks]
    assert indices == list(range(len(indices)))


def test_end_to_end_reglamento() -> None:
    pages = [
        _page(1, "ORD/N° 1/26\nTÍTULO I\nCAPÍTULO I\nDisposiciones generales\n\nEl reglamento rige la vida académica."),
        _page(
            2,
            "ARTÍCULO 1.- Matrícula.\nLos estudiantes deben formalizar la matrícula anual. "
            "La omisión genera la pérdida de cupo. " * 25,
        ),
        _page(
            3,
            "ARTÍCULO 2.- Asistencia.\nLa asistencia a clases es obligatoria en un porcentaje "
            "mínimo establecido por cada facultad. " * 25,
        ),
    ]
    result = chunk_pages(pages)
    assert result.ok
    assert result.total_chunks >= 2
    assert result.total_tokens > 0
    joined = " ".join(c.text for c in result.chunks)
    assert "ARTÍCULO 1" in joined
    assert "ARTÍCULO 2" in joined
    assert all(1 <= c.page_number <= 3 for c in result.chunks)