-- Migración multi-institución (FASE B + A base)
-- Crea tablas de institución, membresía, superadmin y agrega institucion_id a raíz

-- 1. Tipos nuevos
CREATE TYPE IF NOT EXISTS member_type AS ENUM ('ESTUDIANTE', 'ADMIN', 'SECRETARIA');
CREATE TYPE IF NOT EXISTS subscription_state AS ENUM ('TRIAL', 'ACTIVE', 'PENDING_PAYMENT', 'SUSPENDED', 'CANCELLED', 'EXPIRED');
CREATE TYPE IF NOT EXISTS receipt_state AS ENUM ('PENDING', 'COMPLETED', 'FAILED', 'REFUNDED');

-- 2. Instituciones (globales / raíz institucional)
CREATE TABLE IF NOT EXISTS instituciones (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre text NOT NULL,
  nombre_comercial text,
  codigo text UNIQUE,
  email_contacto text,
  telefono_contacto text,
  direccion text,
  ciudad text,
  pais text,
  activo boolean NOT NULL DEFAULT true,
  stripe_customer_id text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- 3. Miembros institucionales (membresía activa única por usuario)
CREATE TABLE IF NOT EXISTS institucion_miembros (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint NOT NULL REFERENCES instituciones(id) ON DELETE CASCADE,
  external_auth_id text NOT NULL REFERENCES app_users(external_auth_id) ON DELETE CASCADE,
  tipo_miembro member_type NOT NULL DEFAULT 'ESTUDIANTE',
  activo boolean NOT NULL DEFAULT true,
  fecha_ingreso timestamptz NOT NULL DEFAULT now(),
  fecha_salida timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (institucion_id, external_auth_id, activo) WHERE activo = true
);
CREATE INDEX idx_institucion_miembros_external_auth_id ON institucion_miembros(external_auth_id);
CREATE INDEX idx_institucion_miembros_institucion_id ON institucion_miembros(institucion_id);

-- 4. Superadmins globales (ortogonal a membresía institucional)
CREATE TABLE IF NOT EXISTS platform_admins (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  external_auth_id text NOT NULL UNIQUE REFERENCES app_users(external_auth_id) ON DELETE CASCADE,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- 5. Planes disponibles (globales)
CREATE TABLE IF NOT EXISTS planes (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  codigo text UNIQUE NOT NULL,
  nombre text NOT NULL,
  descripcion text,
  precio numeric NOT NULL DEFAULT 0,
  moneda character(3) DEFAULT 'USD',
  intervalo text NOT NULL DEFAULT 'monthly',
  max_documentos int DEFAULT 50,
  max_usuarios int DEFAULT 10,
  max_estudiantes int DEFAULT 100,
  features jsonb DEFAULT '{}',
  stripe_product_id text,
  stripe_price_id text,
  activo boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- 6. Suscripciones institucionales
CREATE TABLE IF NOT EXISTS suscripciones (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint NOT NULL REFERENCES instituciones(id) ON DELETE CASCADE,
  plan_id bigint NOT NULL REFERENCES planes(id) ON DELETE SET NULL,
  estado subscription_state NOT NULL DEFAULT 'TRIAL',
  fecha_inicio timestamptz NOT NULL DEFAULT now(),
  fecha_vencimiento timestamptz,
  fecha_cancelacion timestamptz,
  cancelacion_programada boolean NOT NULL DEFAULT false,
  stripe_subscription_id text,
  stripe_customer_id text,
  auto_renovacion boolean NOT NULL DEFAULT true,
  periodo_prueba_inicio timestamptz,
  periodo_prueba_fin timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_suscripciones_institucion_id ON suscripciones(institucion_id);
CREATE INDEX idx_suscripciones_plan_id ON suscripciones(plan_id);

-- 7. Historial de cambios de suscripción
CREATE TABLE IF NOT EXISTS suscripcion_historial (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  suscripcion_id bigint NOT NULL REFERENCES suscripciones(id) ON DELETE CASCADE,
  tipo_evento text NOT NULL,
  plan_anterior_id bigint REFERENCES planes(id) ON DELETE SET NULL,
  plan_nuevo_id bigint REFERENCES planes(id) ON DELETE SET NULL,
  estado_anterior text,
  estado_nuevo text,
  descripcion text,
  external_auth_id text REFERENCES app_users(external_auth_id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- 8. Pagos institucionales
CREATE TABLE IF NOT EXISTS pagos (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint NOT NULL REFERENCES instituciones(id) ON DELETE CASCADE,
  suscripcion_id bigint REFERENCES suscripciones(id) ON DELETE SET NULL,
  importe numeric NOT NULL DEFAULT 0,
  moneda character(3) DEFAULT 'USD',
  estado receipt_state NOT NULL DEFAULT 'PENDING',
  proveedor text,
  stripe_payment_intent_id text,
  stripe_checkout_session_id text,
  stripe_charge_id text,
  idempotency_key text,
  descripcion text,
  fecha_pago timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_pagos_institucion_id ON pagos(institucion_id);
CREATE INDEX idx_pagos_stripe_payment_intent ON pagos(stripe_payment_intent_id);

-- 9. Comprobantes por pago
CREATE TABLE IF NOT EXISTS comprobantes (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint NOT NULL REFERENCES instituciones(id) ON DELETE CASCADE,
  pago_id bigint NOT NULL REFERENCES pagos(id) ON DELETE CASCADE,
  tipo_comprobante text NOT NULL,
  numero text,
  estado receipt_state NOT NULL DEFAULT 'PENDING',
  importe numeric,
  moneda character(3) DEFAULT 'USD',
  archivo_path text,
  proveedor text,
  referencia_externa text,
  fecha_emision timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- 10. Eventos de Stripe (webhook audit)
CREATE TABLE IF NOT EXISTS stripe_eventos (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  stripe_event_id text UNIQUE NOT NULL,
  tipo_evento text NOT NULL,
  payload jsonb DEFAULT '{}',
  procesado boolean NOT NULL DEFAULT false,
  procesado_at timestamptz,
  error text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- 11. Notificaciones institucionales
CREATE TABLE IF NOT EXISTS notificaciones (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint NOT NULL REFERENCES instituciones(id) ON DELETE CASCADE,
  suscripcion_id bigint REFERENCES suscripciones(id) ON DELETE SET NULL,
  tipo text NOT NULL,
  canal text NOT NULL,
  destinatario text,
  asunto text,
  contenido text,
  estado text NOT NULL DEFAULT 'PENDING',
  fecha_programada timestamptz,
  fecha_envio timestamptz,
  error text,
  clave_idempotencia text UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_notificaciones_institucion_id ON notificaciones(institucion_id);
CREATE INDEX idx_notificaciones_suscripcion_id ON notificaciones(suscripcion_id);

-- 12. Configuración SMTP institucional
CREATE TABLE IF NOT EXISTS configuracion_smtp (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint NOT NULL UNIQUE REFERENCES instituciones(id) ON DELETE CASCADE,
  servidor text,
  puerto int DEFAULT 587,
  cifrado text DEFAULT 'tls',
  usuario text,
  password_secret_ref text,
  correo_remitente text,
  nombre_remitente text,
  timeout_segundos int DEFAULT 30,
  activo boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_configuracion_smtp_institucion_id ON configuracion_smtp(institucion_id);

-- 13. Plantillas de email institucional
CREATE TABLE IF NOT EXISTS plantillas_email (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint NOT NULL REFERENCES instituciones(id) ON DELETE CASCADE,
  codigo text NOT NULL,
  nombre text NOT NULL,
  asunto text,
  contenido_html text,
  contenido_texto text,
  activo boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (institucion_id, codigo)
);
CREATE INDEX idx_plantillas_email_institucion_id ON plantillas_email(institucion_id);

-- 14. Adicionar institucion_id a tablas raíz existentes
ALTER TABLE categorias ADD COLUMN IF NOT EXISTS institucion_id bigint REFERENCES instituciones(id) ON DELETE SET NULL;
ALTER TABLE documentos ADD COLUMN IF NOT EXISTS institucion_id bigint NOT NULL DEFAULT 1 REFERENCES instituciones(id) ON DELETE CASCADE; -- luego actualizar el 1 por institución real
ALTER TABLE conversaciones ADD COLUMN IF NOT EXISTS institucion_id bigint NOT NULL DEFAULT 1 REFERENCES instituciones(id) ON DELETE CASCADE;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS institucion_id bigint REFERENCES instituciones(id) ON DELETE SET NULL;
ALTER TABLE feedback ADD COLUMN IF NOT EXISTS institucion_id bigint REFERENCES instituciones(id) ON DELETE SET NULL;
ALTER TABLE audio_interactions ADD COLUMN IF NOT EXISTS institucion_id bigint REFERENCES instituciones(id) ON DELETE SET NULL;
ALTER TABLE pii_mappings ADD COLUMN IF NOT EXISTS institucion_id bigint REFERENCES instituciones(id) ON DELETE SET NULL;

--- Índices nuevos sobre institucion_id ---
CREATE INDEX IF NOT EXISTS idx_categorias_institucion_id ON categorias(institucion_id);
CREATE INDEX IF NOT EXISTS idx_documentos_institucion_id ON documentos(institucion_id);
CREATE INDEX IF NOT EXISTS idx_conversaciones_institucion_id ON conversaciones(institucion_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_institucion_id ON audit_logs(institucion_id);
CREATE INDEX IF NOT EXISTS idx_feedback_institucion_id ON feedback(institucion_id);
CREATE INDEX IF NOT EXISTS idx_audio_interactions_institucion_id ON audio_interactions(institucion_id);
CREATE INDEX IF NOT EXISTS idx_pii_mappings_institucion_id ON pii_mappings(institucion_id);

-- Reemplazo de match_document_chunks con aislamiento institucional y versión activa
CREATE OR REPLACE FUNCTION match_document_chunks (
  query_embedding vector(1536),
  match_count int default 5,
  similarity_threshold float default 0.0,
  p_institucion_id bigint
)
RETURNS table (
  chunk_id bigint,
  document_id bigint,
  document_version_id bigint,
  document_title text,
  page_number int,
  chunk_text text,
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    dc.id as chunk_id,
    d.id as document_id,
    dv.id as document_version_id,
    d.titulo as document_title,
    dc.page_number,
    dc.chunk_text,
    1 - (de.embedding <=> query_embedding) as similarity
  FROM document_embeddings de
  JOIN document_chunks dc ON dc.id = de.chunk_id
  JOIN documento_versiones dv ON dv.id = dc.documento_version_id
  JOIN documentos d ON d.id = dv.documento_id
  WHERE
    d.activo = true
    AND dv.status = 'READY'
    AND dv.es_version_activa = true
    AND d.institucion_id = p_institucion_id
    AND (1 - (de.embedding <=> query_embedding)) >= similarity_threshold
  ORDER BY de.embedding <=> query_embedding
  LIMIT match_count;
$$;

-- FASE C: Ajuste de categorias (constraint único + seed + NOT NULL)
ALTER TABLE categorias DROP CONSTRAINT IF EXISTS categorias_nombre_key;
ALTER TABLE categorias ADD CONSTRAINT categorias_nombre_institucion_unique UNIQUE (nombre, institucion_id);
UPDATE categorias SET institucion_id = 1 WHERE institucion_id IS NULL;
ALTER TABLE categorias ALTER COLUMN institucion_id SET NOT NULL;
