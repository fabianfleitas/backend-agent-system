from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import DocumentOut, DocumentVersionOut


class MemberIn(BaseModel):
    external_auth_id: str
    tipo_miembro: str = "ESTUDIANTE"

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
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

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
    institucion_id: int
    fecha_creacion: datetime


class AdminReindexIn(BaseModel):
    documento_id: Optional[int] = Field(default=None)


class AdminReindexOut(BaseModel):
    updated_versions: int
