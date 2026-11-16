from __future__ import annotations

from typing import Any, Optional

from app.repositories.config_repository import ConfigParametersRepository


class FakeResponse:
    def __init__(self, data: Optional[list[dict]] = None) -> None:
        self.data = data or []


class FakeTable:
    def __init__(self, client: "FakeClient") -> None:
        self.client = client
        self.op: Optional[str] = None
        self.filters: list[tuple[str, Any]] = []
        self.payload: Optional[dict] = None
        self.on_conflict: Optional[str] = None

    def select(self, *args, **kwargs) -> "FakeTable":
        self.op = "select"
        return self

    def eq(self, key: str, value: Any) -> "FakeTable":
        self.filters.append((key, value))
        return self

    def order(self, *args, **kwargs) -> "FakeTable":
        return self

    def limit(self, *args, **kwargs) -> "FakeTable":
        return self

    def update(self, payload: dict) -> "FakeTable":
        self.op = "update"
        self.payload = payload
        return self

    def insert(self, payload: dict) -> "FakeTable":
        self.op = "insert"
        self.payload = payload
        return self

    def upsert(self, payload: dict, on_conflict: Optional[str] = None) -> "FakeTable":
        self.op = "upsert"
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def execute(self) -> FakeResponse:
        self.client.ops.append(self)
        rows = self.client.rows
        if self.op == "select":
            selected = [
                row for row in rows
                if all(row.get(key) == value for key, value in self.filters)
            ]
            return FakeResponse([dict(row) for row in selected])

        if self.op == "insert":
            row = dict(self.payload or {})
            row.setdefault("id", len(rows) + 1)
            rows.append(row)
            return FakeResponse([dict(row)])

        if self.op == "upsert":
            payload = dict(self.payload or {})
            for row in rows:
                if (
                    row.get("clave") == payload.get("clave")
                    and row.get("institucion_id") == payload.get("institucion_id")
                ):
                    row.update(payload)
                    return FakeResponse([dict(row)])
            payload.setdefault("id", len(rows) + 1)
            rows.append(payload)
            return FakeResponse([dict(payload)])

        if self.op == "update":
            payload = dict(self.payload or {})
            for row in rows:
                if all(row.get(key) == value for key, value in self.filters):
                    row.update(payload)
                    return FakeResponse([dict(row)])
            return FakeResponse([])

        raise AssertionError(f"operación no soportada: {self.op}")


class FakeClient:
    def __init__(self, rows: Optional[list[dict]] = None) -> None:
        self.rows = rows or []
        self.ops: list[FakeTable] = []

    def table(self, name: str) -> FakeTable:
        return FakeTable(self)


def _repo(rows: list[dict]) -> tuple[ConfigParametersRepository, FakeClient]:
    client = FakeClient(rows)
    return ConfigParametersRepository(client=client), client  # type: ignore[arg-type]


def test_get_param_prefiere_institucional_sobre_global() -> None:
    repo, _ = _repo([
        {"id": 1, "clave": "llm_model", "valor": "global/model", "institucion_id": None, "activo": True},
        {"id": 2, "clave": "llm_model", "valor": "inst/model", "institucion_id": 1, "activo": True},
    ])

    assert repo.get_param("llm_model", 1)["valor"] == "inst/model"
    assert repo.get_param("llm_model", 99)["valor"] == "global/model"
    assert repo.get_param("llm_model", None)["valor"] == "global/model"


def test_set_param_institucional_usa_on_conflict_valido() -> None:
    repo, client = _repo([])

    result = repo.set_param("llm_model", "inst/model", "string", institucion_id=1)

    assert result is not None
    assert result["valor"] == "inst/model"
    assert client.ops[-1].on_conflict == "institucion_id,clave"


def test_set_param_global_actualiza_sin_duplicar() -> None:
    repo, client = _repo([
        {"id": 10, "clave": "judge_model", "valor": "old/model", "institucion_id": None, "activo": True},
    ])

    result = repo.set_param("judge_model", "new/model", "string", institucion_id=None)

    assert result is not None
    assert result["valor"] == "new/model"
    assert len([row for row in client.rows if row["clave"] == "judge_model"]) == 1


def test_set_param_global_inserta_si_no_existe() -> None:
    repo, client = _repo([])

    result = repo.set_param("llm_model", "new/model", "string", institucion_id=None)

    assert result is not None
    assert client.ops[-1].op == "insert"
    assert len(client.rows) == 1
