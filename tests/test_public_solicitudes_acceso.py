from __future__ import annotations

"""Tests de POST /api/public/solicitudes-acceso (formulario público de acceso)."""

from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.public.routes import router as public_router
from app.core.config import settings
from app.schemas.solicitudes import SolicitudAccesoIn
from app.services.solicitudes_acceso_service import SolicitudAccesoService

_SIN_DEFINIR = object()

VALIDO = {
    "institucion_nombre": "Universidad Ejemplo",
    "persona_contacto": "Ana Pérez",
    "email": "ana@ejemplo.edu.py",
    "telefono": "+595981000000",
    "cantidad_usuarios_estimada": 1200,
    "perfil_solicitado": "ADMINISTRACION",
    "mensaje": "Necesitamos habilitar el panel para secretaría.",
    "consentimiento": True,
    "empresa": "",
}


class FakeService:
    def __init__(self, resultado=_SIN_DEFINIR) -> None:
        self.creadas: list = []
        self.resultado = (
            {
                "id": 7,
                "estado": "PENDIENTE",
                "created_at": "2026-10-04T00:00:00+00:00",
            }
            if resultado is _SIN_DEFINIR
            else resultado
        )

    def crear(self, payload, origen: str = "desconocido"):
        self.creadas.append((payload, origen))
        return self.resultado


def _client(monkeypatch, fake: FakeService) -> TestClient:
    monkeypatch.setattr("app.api.public.routes.SolicitudAccesoService", lambda: fake)
    app = FastAPI()
    app.include_router(public_router, prefix="/api/public")
    return TestClient(app)


def test_crea_solicitud_valida(monkeypatch):
    fake = FakeService()
    res = _client(monkeypatch, fake).post("/api/public/solicitudes-acceso", json=VALIDO)

    assert res.status_code == 201
    body = res.json()
    assert body["id"] == 7
    assert body["estado"] == "PENDIENTE"
    assert len(fake.creadas) == 1


def test_no_expone_datos_personales(monkeypatch):
    fake = FakeService()
    res = _client(monkeypatch, fake).post("/api/public/solicitudes-acceso", json=VALIDO)

    body = res.json()
    assert "email" not in body
    assert "telefono" not in body
    assert body["created_at"] is not None


@pytest.mark.parametrize(
    "cambio",
    [
        {"consentimiento": False},
        {"email": "no-es-un-correo"},
        {"institucion_nombre": "X"},
        {"persona_contacto": ""},
        {"perfil_solicitado": "OTRO"},
        {"cantidad_usuarios_estimada": 0},
    ],
)
def test_rechaza_payload_invalido(monkeypatch, cambio):
    fake = FakeService()
    res = _client(monkeypatch, fake).post(
        "/api/public/solicitudes-acceso", json={**VALIDO, **cambio}
    )

    assert res.status_code == 422
    assert fake.creadas == []


def test_honeypot_responde_como_exito(monkeypatch):
    fake = FakeService(resultado=None)
    res = _client(monkeypatch, fake).post("/api/public/solicitudes-acceso", json=VALIDO)

    assert res.status_code == 201
    assert res.json()["id"] == 0


class FakeRepo:
    def __init__(self) -> None:
        self.payloads: list = []

    def create(self, payload: dict) -> dict:
        self.payloads.append(payload)
        return {"id": 42, **payload, "created_at": "2026-10-04T00:00:00+00:00"}


class FakeNotifier:
    def __init__(self, raises: bool = False) -> None:
        self.calls: list = []
        self.raises = raises

    def send_automated(self, institucion_id, **kwargs):
        if self.raises:
            raise RuntimeError("SMTP caído")
        self.calls.append((institucion_id, kwargs))
        return {"id": 1}


def _payload(**over) -> SolicitudAccesoIn:
    return SolicitudAccesoIn(**{**VALIDO, **over})


def test_servicio_detecta_honeypot(monkeypatch):
    repo, notifier = FakeRepo(), FakeNotifier()
    svc = SolicitudAccesoService(repo=repo, notifier=notifier)

    assert svc.crear(_payload(empresa="http://spam.example")) is None
    assert repo.payloads == []
    assert notifier.calls == []


def test_servicio_persiste_y_avisa(monkeypatch):
    monkeypatch.setattr(settings, "solicitudes_email", "equipo@voxia.py")
    repo, notifier = FakeRepo(), FakeNotifier()
    svc = SolicitudAccesoService(repo=repo, notifier=notifier)

    solicitud = svc.crear(_payload(), origen="https://landing.example")

    assert solicitud["id"] == 42
    assert repo.payloads[0]["estado"] == "PENDIENTE"
    assert repo.payloads[0]["origen"] == "https://landing.example"
    assert repo.payloads[0]["email"] == "ana@ejemplo.edu.py"
    assert len(notifier.calls) == 1
    assert notifier.calls[0][1]["destinatario"] == "equipo@voxia.py"


def test_servicio_sin_correo_configurado_no_avisa(monkeypatch):
    monkeypatch.setattr(settings, "solicitudes_email", "")
    repo, notifier = FakeRepo(), FakeNotifier()
    svc = SolicitudAccesoService(repo=repo, notifier=notifier)

    solicitud = svc.crear(_payload())

    assert solicitud["id"] == 42
    assert len(repo.payloads) == 1
    assert notifier.calls == []


def test_aviso_falla_suave(monkeypatch):
    monkeypatch.setattr(settings, "solicitudes_email", "equipo@voxia.py")
    repo, notifier = FakeRepo(), FakeNotifier(raises=True)
    svc = SolicitudAccesoService(repo=repo, notifier=notifier)

    solicitud = svc.crear(_payload())

    assert solicitud["id"] == 42
    assert len(repo.payloads) == 1
