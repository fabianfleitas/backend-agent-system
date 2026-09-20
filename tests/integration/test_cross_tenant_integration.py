from __future__ import annotations

import pytest

# Solo se ejecuta con -m integration y con env configurado
pytest.importorskip("supabase")


def test_integration_membership_unique_constraint():
    # Verifica que el índice parcial 004 rechaza segunda membresía activa
    # Requiere conexión real a Supabase con datos de prueba
    pytest.skip("Requiere SUPABASE_URL + SERVICE_ROLE_KEY configurados; ver docs/qa/seed_qa.sql")
