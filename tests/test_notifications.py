from __future__ import annotations

"""Tests para notificaciones/SMTP (GET/PUT /api/admin/smtp, GET notifications, send-test)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin.notifications_routes import router as notifications_router
from app.core.security import AuthContext, get_auth_context
from app.services.notification_service import NotificationService


def _make_app(auth: AuthContext):
    app = FastAPI()
    app.include_router(notifications_router, prefix="/api/admin")
    app.dependency_overrides[get_auth_context] = lambda: auth
    return app


def _apply_fake(monkeypatch, svc):
    monkeypatch.setattr("app.api.admin.notifications_routes.NotificationService", lambda: svc)


def _admin() -> AuthContext:
    return AuthContext(external_auth_id="a", institucion_id=1, tipo_miembro="ADMIN")


SMTP = {
    "institucion_id": 1,
    "servidor": "smtp.test.local",
    "puerto": 587,
    "cifrado": "STARTTLS",
    "usuario": "u",
    "correo_remitente": "no-reply@inst.edu",
    "nombre_remitente": "Sistema",
    "timeout_segundos": 30,
    "activo": True,
}

NOTIFICATION = {
    "id": 1,
    "institucion_id": 1,
    "tipo": "SYSTEM",
    "canal": "EMAIL",
    "destinatario": "a@inst.edu",
    "asunto": "Prueba",
    "contenido": "Mensaje",
    "estado": "SENT",
    "created_at": "2026-01-01T00:00:00Z",
}


class FakeNotificationService:
    def __init__(self):
        self.calls = []

    def get_smtp_config(self, auth=None):
        self.calls.append("get_smtp_config")
        return dict(SMTP)

    def update_smtp_config(self, auth, payload):
        self.calls.append(("update_smtp_config", payload.servidor))
        return dict(SMTP, servidor=payload.servidor)

    def list_notifications(self, auth):
        self.calls.append("list_notifications")
        return [dict(NOTIFICATION)]

    def send_test(self, auth, email, asunto, mensaje):
        self.calls.append(("send_test", email))
        return dict(NOTIFICATION)


def test_get_smtp(monkeypatch):
    svc = FakeNotificationService()
    _apply_fake(monkeypatch, svc)
    app = _make_app(_admin())
    resp = TestClient(app).get("/api/admin/smtp")
    assert resp.status_code == 200
    assert resp.json()["servidor"] == "smtp.test.local"


def test_update_smtp(monkeypatch):
    svc = FakeNotificationService()
    _apply_fake(monkeypatch, svc)
    app = _make_app(_admin())
    payload = {
        "servidor": "smtp2.test.local",
        "puerto": 587,
        "cifrado": "STARTTLS",
        "correo_remitente": "no-reply@inst.edu",
    }
    resp = TestClient(app).put("/api/admin/smtp", json=payload)
    assert resp.status_code == 200
    assert resp.json()["servidor"] == "smtp2.test.local"
    assert svc.calls[0][0] == "update_smtp_config"


def test_list_notifications(monkeypatch):
    svc = FakeNotificationService()
    _apply_fake(monkeypatch, svc)
    app = _make_app(_admin())
    resp = TestClient(app).get("/api/admin/notifications")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"]["total"] == 1
    assert body["items"][0]["destinatario"] == "a@inst.edu"


def test_send_test(monkeypatch):
    svc = FakeNotificationService()
    _apply_fake(monkeypatch, svc)
    app = _make_app(_admin())
    resp = TestClient(app).post("/api/admin/notifications/send-test", json={"email": "x@y.z"})
    assert resp.status_code == 200
    assert resp.json()["estado"] == "SENT"
    assert svc.calls[0][0] == "send_test"


def test_notifications_blocks_platform_admin_without_membership(monkeypatch):
    auth = AuthContext(external_auth_id="pa", institucion_id=None, tipo_miembro=None, is_platform_admin=True)
    svc = FakeNotificationService()
    _apply_fake(monkeypatch, svc)
    app = _make_app(auth)
    assert TestClient(app).get("/api/admin/notifications").status_code == 403
    assert TestClient(app).post("/api/admin/notifications/send-test", json={"email": "x@y.z"}).status_code == 403


# --- Service level ---

def test_notification_service_send_email_marks_sent(monkeypatch):
    class FakeNotificationsRepo:
        def __init__(self):
            self.created = None
            self.sent = None

        def get_by_idempotency(self, clave):
            return None

        def create(self, payload):
            self.created = payload
            return {"id": 7, **payload}

        def mark_sent(self, notification_id, fecha_envio):
            self.sent = notification_id
            return {"id": notification_id, "estado": "SENT", "fecha_envio": fecha_envio}

        def mark_failed(self, notification_id, error):
            return {"id": notification_id, "estado": "FAILED", "error": error}

        def list_by_institution(self, institucion_id):
            return []

    class FakeSmtpRepo:
        def get_config(self, institucion_id):
            return dict(SMTP)

        def upsert(self, *a, **k):
            return dict(SMTP)

    class FakeTemplatesRepo:
        def get_template(self, codigo, institucion_id):
            return None

    repo = FakeNotificationsRepo()
    svc = NotificationService(
        notifications_repo=repo,
        smtp_repo=FakeSmtpRepo(),
        templates_repo=FakeTemplatesRepo(),
    )
    # Patchear _send_smtp para no abrir conexión real
    monkeypatch.setattr(svc, "_send_smtp", lambda config, to, subject, html, text: None)
    result = svc.send_email(
        _admin(),
        destinatario="a@inst.edu",
        asunto="Hola",
        contenido="<p>Hola</p>",
        contenido_texto="Hola",
        clave_idempotencia="abc-1",
    )
    assert result["estado"] == "SENT"
    assert repo.sent == 7
    assert repo.created["canal"] == "EMAIL"


def test_notification_service_send_email_marks_failed_when_no_smtp(monkeypatch):
    class FakeNotificationsRepo:
        def __init__(self):
            self.failed = None

        def get_by_idempotency(self, clave):
            return None

        def create(self, payload):
            return {"id": 9, **payload}

        def mark_failed(self, notification_id, error):
            self.failed = (notification_id, error)
            return {"id": notification_id, "estado": "FAILED", "error": error}

    class FakeSmtpRepo:
        def get_config(self, institucion_id):
            return None

    svc = NotificationService(
        notifications_repo=FakeNotificationsRepo(),
        smtp_repo=FakeSmtpRepo(),
        templates_repo=object(),
    )
    result = svc.send_email(_admin(), destinatario="a@inst.edu", asunto="Hola", contenido="Hola")
    assert result["estado"] == "FAILED"