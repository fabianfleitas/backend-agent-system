from __future__ import annotations

import pytest

from app.repositories.institutions_repository import InstitutionsRepository


class FakeSupabaseClient:
    def __init__(self, data_map: dict = None) -> None:
        self.data_map = data_map or {}
        self.calls = []

    def table(self, name: str):
        self.calls.append(name)
        return self

    def select(self, *cols):
        return self

    def eq(self, col, val):
        self.calls.append(("eq", col, val))
        return self

    def is_(self, col, val):
        self.calls.append(("is_", col, val))
        return self

    def limit(self, n):
        return self

    def order(self, col, desc=False):
        return self

    def in_(self, col, vals):
        return self

    def update(self, fields):
        return self

    def insert(self, payload):
        return self

    def execute(self):
        class Resp:
            data = self.data_map.get("last", [])
        return Resp()


def test_institutions_repository_get_active_membership_found():
    repo = InstitutionsRepository(client=FakeSupabaseClient({"last": [{"institucion_id": 1, "tipo_miembro": "ADMIN"}]}))
    result = repo.get_active_membership("user-1")
    assert result is not None
    assert result["institucion_id"] == 1
