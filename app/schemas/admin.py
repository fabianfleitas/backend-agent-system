from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import DocumentOut, DocumentVersionOut


class MemberIn(BaseModel):
    external_auth_id: str
    tipo_miembro: str = "ESTUDIANTE"


class UserCreateIn(BaseModel):
    external_auth_id: str
    email: str
    full_name: Optional[str] = None
    institucion_id: Optional[int] = None
    tipo_miembro: str = "ESTUDIANTE"


class PlatformAdminIn(BaseModel):
    external_auth_id: str


class PlatformAdminOut(BaseModel):
    external_auth_id: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None

class InstitutionIn(BaseModel):
    codigo: Optional[str] = None
    nombre: str
    nombre_comercial: Optional[str] = None
    ciudad: Optional[str] = None
    pais: Optional[str] = None
    direccion: Optional[str] = None
    email_contacto: Optional[str] = None
    telefono_contacto: Optional[str] = None

class MemberOut(BaseModel):
    id: int
    external_auth_id: str
    tipo_miembro: str
    activo: bool = True
    fecha_ingreso: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None

class InstitutionOut(BaseModel):
    id: int
    codigo: Optional[str] = None
    nombre: str
    nombre_comercial: Optional[str] = None
    ciudad: Optional[str] = None
    pais: Optional[str] = None
    direccion: Optional[str] = None
    email_contacto: Optional[str] = None
    telefono_contacto: Optional[str] = None
    activo: bool = True
    stripe_customer_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class PlanOut(BaseModel):
    id: int
    codigo: Optional[str] = None
    nombre: str
    descripcion: Optional[str] = None
    precio: Optional[float] = None
    moneda: Optional[str] = None
    intervalo: Optional[str] = None
    max_documentos: Optional[int] = None
    max_usuarios: Optional[int] = None
    max_estudiantes: Optional[int] = None
    features: Optional[dict] = None
    activo: bool = True
    stripe_product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PlanIn(BaseModel):
    codigo: Optional[str] = None
    nombre: str
    descripcion: Optional[str] = None
    precio: Optional[float] = None
    moneda: Optional[str] = None
    intervalo: Optional[str] = None
    max_documentos: Optional[int] = None
    max_usuarios: Optional[int] = None
    max_estudiantes: Optional[int] = None
    features: Optional[dict] = None


class StripePlanSyncIn(BaseModel):
    plan_id: int


class StripePlanSyncOut(BaseModel):
    plan_id: int
    stripe_product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    stripe_product_created: bool = False
    stripe_price_created: bool = False


class SubscriptionCreateIn(BaseModel):
    plan_id: int


class SubscriptionCreateOut(BaseModel):
    subscription_id: str
    customer_id: str
    status: Optional[str] = None
    latest_invoice_payment_intent_id: Optional[str] = None
    client_secret: Optional[str] = None


class SubscriptionCancelIn(BaseModel):
    cancel_at_period_end: bool = True


class SubscriptionActionOut(BaseModel):
    subscription_id: str
    customer_id: Optional[str] = None
    status: Optional[str] = None
    cancel_at_period_end: bool = False
    canceled_at: Optional[str] = None


class CheckoutSessionIn(BaseModel):
    plan_id: int
    success_url: str = "https://example.com/success"
    cancel_url: str = "https://example.com/cancel"

class CheckoutSessionOut(BaseModel):
    url: Optional[str] = None
    session_id: Optional[str] = None

class StripeSubscriptionOut(BaseModel):
    subscription_id: str
    customer_id: Optional[str] = None
    status: Optional[str] = None
    cancel_at_period_end: bool = False
    current_period_end: Optional[str] = None
    current_period_start: Optional[str] = None
    latest_invoice_payment_intent_id: Optional[str] = None
    latest_invoice_status: Optional[str] = None


class StripePortalSessionIn(BaseModel):
    return_url: str


class StripePortalSessionOut(BaseModel):
    url: str
    id: Optional[str] = None
    customer_id: Optional[str] = None


class SubscriptionChangePlanIn(BaseModel):
    plan_id: int


class SubscriptionChangePlanOut(BaseModel):
    subscription_id: str
    customer_id: Optional[str] = None
    status: Optional[str] = None
    latest_invoice_payment_intent_id: Optional[str] = None
    client_secret: Optional[str] = None

class SubscriptionOut(BaseModel):
    id: int
    institucion_id: Optional[int] = None
    plan_id: int
    estado: Optional[str] = None
    fecha_inicio: Optional[str] = None
    fecha_vencimiento: Optional[str] = None
    fecha_cancelacion: Optional[str] = None
    cancelacion_programada: bool = False
    auto_renovacion: bool = False
    periodo_prueba_inicio: Optional[str] = None
    periodo_prueba_fin: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    plan: Optional[PlanOut] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class PagoOut(BaseModel):
    id: int
    institucion_id: Optional[int] = None
    suscripcion_id: Optional[int] = None
    importe: Optional[float] = None
    moneda: Optional[str] = None
    estado: Optional[str] = None
    proveedor: Optional[str] = None
    descripcion: Optional[str] = None
    fecha_pago: Optional[str] = None
    created_at: Optional[str] = None

class SubscriptionHistoryOut(BaseModel):
    id: int
    suscripcion_id: int
    tipo_evento: Optional[str] = None
    estado_anterior: Optional[str] = None
    estado_nuevo: Optional[str] = None
    plan_anterior_id: Optional[int] = None
    plan_nuevo_id: Optional[int] = None
    descripcion: Optional[str] = None
    external_auth_id: Optional[str] = None
    created_at: Optional[str] = None

class ComprobanteOut(BaseModel):
    id: int
    institucion_id: Optional[int] = None
    pago_id: Optional[int] = None
    tipo_comprobante: Optional[str] = None
    numero: Optional[str] = None
    estado: Optional[str] = None
    importe: Optional[float] = None
    moneda: Optional[str] = None
    archivo_path: Optional[str] = None
    proveedor: Optional[str] = None
    referencia_externa: Optional[str] = None
    fecha_emision: Optional[str] = None
    created_at: Optional[str] = None

class ConfigParamIn(BaseModel):
    clave: str
    valor: str
    tipo: str = "string"
    descripcion: Optional[str] = None


class EmailTemplateOut(BaseModel):
    id: int
    institucion_id: Optional[int] = None
    codigo: str
    nombre: str
    asunto: str
    contenido_html: Optional[str] = None
    contenido_texto: Optional[str] = None
    activo: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class EmailTemplateIn(BaseModel):
    codigo: str
    nombre: str
    asunto: str
    contenido_html: Optional[str] = None
    contenido_texto: Optional[str] = None
    activo: bool = True


class SmtpConfigOut(BaseModel):
    institucion_id: Optional[int] = None
    servidor: str
    puerto: int = 587
    cifrado: str = "STARTTLS"
    usuario: Optional[str] = None
    correo_remitente: str
    nombre_remitente: Optional[str] = None
    timeout_segundos: int = 30
    activo: bool = True


class SmtpConfigIn(BaseModel):
    servidor: str
    puerto: int = 587
    cifrado: str = "STARTTLS"
    usuario: Optional[str] = None
    password: Optional[str] = None
    correo_remitente: str
    nombre_remitente: Optional[str] = None
    timeout_segundos: int = 30
    activo: bool = True


class NotificationOut(BaseModel):
    id: int
    institucion_id: Optional[int] = None
    tipo: str = "SYSTEM"
    canal: str = "EMAIL"
    destinatario: str
    asunto: Optional[str] = None
    contenido: Optional[str] = None
    estado: str = "PENDING"
    fecha_programada: Optional[str] = None
    fecha_envio: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[str] = None


class SendTestIn(BaseModel):
    email: str
    asunto: Optional[str] = None
    mensaje: Optional[str] = None


class AdminFeedbackOut(BaseModel):
    id: int
    message_id: int
    conversacion_id: Optional[int] = None
    rating: int
    comment: Optional[str] = None
    external_auth_id: Optional[str] = None
    contenido_texto: Optional[str] = None
    audit_id: Optional[str] = None
    created_at: Optional[str] = None

class ConfigParamOut(BaseModel):
    id: int
    institucion_id: Optional[int]
    clave: str
    valor: str
    tipo: str
    descripcion: Optional[str]
    editable_desde_dashboard: bool
    activo: bool
    created_at: Optional[str]
    updated_at: Optional[str]

class AdminUploadDocumentOut(BaseModel):
    document: DocumentOut
    version: DocumentVersionOut


class AdminUploadVersionOut(BaseModel):
    document: DocumentOut
    version: DocumentVersionOut


class DocumentDetailOut(BaseModel):
    id: int
    categoria_id: Optional[int] = None
    codigo_documento: Optional[str] = None
    titulo: str
    descripcion: Optional[str] = None
    activo: bool = True
    fecha_creacion: str
    versiones: List[DocumentVersionOut] = []


class CategoryOut(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    activo: bool = True
    institucion_id: Optional[int] = None
    fecha_creacion: datetime


class CategoryIn(BaseModel):
    nombre: str
    descripcion: Optional[str] = None

class AdminReindexIn(BaseModel):
    documento_id: Optional[int] = Field(default=None)


class AdminReindexOut(BaseModel):
    updated_versions: int


class EscalamientoOut(BaseModel):
    id: int
    institucion_id: Optional[int] = None
    motivo: str
    resumen: Optional[str] = None
    conversacion_id: Optional[int] = None
    mensaje_id: Optional[int] = None
    audit_id: Optional[str] = None
    external_auth_id: Optional[str] = None
    workflow_estado: str = "PENDING"
    resolved_by: Optional[str] = None
    resolved_at: Optional[str] = None
    created_at: Optional[str] = None
