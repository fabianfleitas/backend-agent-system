from __future__ import annotations

"""Tests de persistencia y recuperación (RF-08: persistencia local).

Verifican, a través de los repositorios reales, que las conversaciones y los
mensajes se persisten y se recuperan en consultas posteriores. Usan un cliente
Supabase fake en memoria que emula la API encadenada (`table().insert()...`),
por lo que no requieren base de datos.

Ejecutar:
    python3 -m pytest tests/test_persistence.py
"""

from typing import Any, Optional

from app.repositories.conversations_repository import ConversationsRepository
from app.repositories.messages_repository import MessagesRepository


class _Resp:
    def __init__(self, data: list[dict]) -> None:
        self.data = data


class _FakeQuery:
    def __init__(self, store: dict[str, list[dict]], table: str, defaults: Optional[dict] = None) -> None:
        self._store = store
        self._table = table
        self._defaults = defaults or {}
        self._op: Optional[str] = None
        self._payload: Any = None
        self._filters: list[tuple[str, Any]] = []
        self._order: Optional[tuple[str, bool]] = None
        self._limit: Optional[int] = None

    def select(self, *cols: str) -> "_FakeQuery":
        self._op = "select"
        return self

    def insert(self, payload: dict) -> "_FakeQuery":
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, fields: dict) -> "_FakeQuery":
        self._op = "update"
        self._payload = fields
        return self

    def eq(self, col: str, val: Any) -> "_FakeQuery":
        self._filters.append((col, val))
        return self

    def order(self, col: str, desc: bool = False) -> "_FakeQuery":
        self._order = (col, desc)
        return self

    def limit(self, n: int) -> "_FakeQuery":
        self._limit = n
        return self

    def execute(self) -> _Resp:
        rows = self._store.setdefault(self._table, [])
        if self._op == "insert":
            row = {**self._defaults, **self._payload}
            row.setdefault("id", self._store[f"{self._table}__seq"] + 1)  # type: ignore[index]
            self._store[f"{self._table}__seq"] = row["id"]  # type: ignore[index]
            rows.append(row)
            return _Resp([row])
        if self._op == "update":
            updated = []
            for row in rows:
                if all(row.get(c) == v for c, v in self._filters):
                    row.update(self._payload)
                    updated.append(row)
            return _Resp(updated)
        result = [r for r in rows if all(r.get(c) == v for c, v in self._filters)]
        if self._order:
            col, desc = self._order
            result = sorted(result, key=lambda r: r.get(col) or "", reverse=desc)
        if self._limit is not None:
            result = result[: self._limit]
        return _Resp(result)


class FakeSupabase:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}
        # Defaults equivalentes a los del esquema real (p. ej. conversaciones.hidden).
        self.defaults = {"conversaciones": {"hidden": False}}

    def table(self, name: str) -> _FakeQuery:
        self.store.setdefault(f"{name}__seq", 0)
        return _FakeQuery(self.store, name, self.defaults.get(name, {}))


def test_conversation_persistence_roundtrip() -> None:
    client = FakeSupabase()
    repo = ConversationsRepository(client=client)

    created = repo.create_conversation("user-1", "Consulta de matrícula", institucion_id=3)
    assert created["id"] == 1
    assert created["external_auth_id"] == "user-1"
    assert created["institucion_id"] == 3

    fetched = repo.get_conversation(created["id"], institucion_id=3)
    assert fetched is not None
    assert fetched["title"] == "Consulta de matrícula"

    # Aislamiento: no se recupera con otra institución.
    assert repo.get_conversation(created["id"], institucion_id=99) is None


def test_message_persistence_and_count() -> None:
    client = FakeSupabase()
    repo = MessagesRepository(client=client)

    first = repo.create_message(1, "user-1", "USER", "¿Cuándo abren las inscripciones?")
    second = repo.create_message(1, "user-1", "ASSISTANT", "A partir del 1 de marzo.")
    assert first["id"] == 1 and second["id"] == 2

    messages = repo.get_conversation_messages(1)
    assert [m["contenido_texto"] for m in messages] == [
        "¿Cuándo abren las inscripciones?",
        "A partir del 1 de marzo.",
    ]
    assert repo.count_conversation_messages(1) == 2
    # Otro hilo no ve estos mensajes.
    assert repo.count_conversation_messages(2) == 0


def test_message_audit_and_update() -> None:
    client = FakeSupabase()
    repo = MessagesRepository(client=client)
    msg = repo.create_message(1, "user-1", "ASSISTANT", "respuesta")

    updated = repo.update_message_audit_id(msg["id"], "audit-123")
    assert updated is not None and updated["audit_id"] == "audit-123"

    changed = repo.update_message(msg["id"], contenido_texto="respuesta editada")
    assert changed is not None and changed["contenido_texto"] == "respuesta editada"


def test_list_conversations_excludes_hidden_by_default() -> None:
    client = FakeSupabase()
    repo = ConversationsRepository(client=client)

    visible = repo.create_conversation("user-1", "Visible", institucion_id=1)
    hidden = repo.create_conversation("user-1", "Oculta", institucion_id=1)

    # Ocultar = baja lógica; el registro persiste.
    repo.hide_conversation("user-1", hidden["id"], institucion_id=1)

    listed = repo.list_conversations("user-1", include_hidden=False, institucion_id=1)
    ids = {c["id"] for c in listed}
    assert visible["id"] in ids
    assert hidden["id"] not in ids

    all_listed = repo.list_conversations("user-1", include_hidden=True, institucion_id=1)
    assert {c["id"] for c in all_listed} == {visible["id"], hidden["id"]}
