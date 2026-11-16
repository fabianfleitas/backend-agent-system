-- Esquema mínimo y reproducible para pruebas locales con Supabase.
--
-- No es una migración de producción ni reemplaza a migrations/*.sql. Se aplica
-- únicamente a una instancia Supabase local desechable antes de sembrar un
-- usuario/institución sintéticos. No contiene datos reales.
--
-- Uso (con el contenedor local activo):
--   docker exec -i supabase_db_<proyecto> psql -U postgres -d postgres \
--     < eval/local_supabase_schema.sql

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS app_users (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  external_auth_id text NOT NULL UNIQUE,
  email text NOT NULL,
  full_name text,
  role text NOT NULL DEFAULT 'STUDENT'
    CHECK (role IN ('STUDENT', 'ADMIN', 'STAFF')),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS instituciones (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre text NOT NULL,
  nombre_comercial text,
  codigo text UNIQUE,
  email_contacto text,
  telefono_contacto text,
  direccion text,
  ciudad text,
  pais text DEFAULT 'Paraguay',
  activo boolean NOT NULL DEFAULT true,
  stripe_customer_id text UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS planes (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  codigo text NOT NULL UNIQUE,
  nombre text NOT NULL,
  descripcion text,
  precio numeric NOT NULL DEFAULT 0 CHECK (precio >= 0),
  moneda character(3) NOT NULL DEFAULT 'USD',
  intervalo text NOT NULL DEFAULT 'MONTH' CHECK (intervalo IN ('MONTH', 'YEAR')),
  max_documentos integer,
  max_usuarios integer,
  max_estudiantes integer,
  features jsonb NOT NULL DEFAULT '{}'::jsonb,
  stripe_product_id text UNIQUE,
  stripe_price_id text UNIQUE,
  activo boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS institucion_miembros (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint NOT NULL REFERENCES instituciones(id) ON DELETE CASCADE,
  external_auth_id text NOT NULL REFERENCES app_users(external_auth_id) ON DELETE CASCADE,
  tipo_miembro text NOT NULL DEFAULT 'ESTUDIANTE'
    CHECK (tipo_miembro IN ('ADMIN', 'SECRETARIA', 'ESTUDIANTE', 'STUDENT')),
  activo boolean NOT NULL DEFAULT true,
  fecha_ingreso timestamptz NOT NULL DEFAULT now(),
  fecha_salida timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS platform_admins (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  external_auth_id text NOT NULL UNIQUE REFERENCES app_users(external_auth_id) ON DELETE CASCADE,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS categorias (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre text NOT NULL,
  descripcion text,
  activo boolean NOT NULL DEFAULT true,
  fecha_creacion timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  institucion_id bigint REFERENCES instituciones(id) ON DELETE SET NULL,
  orden integer DEFAULT 0,
  fecha_baja timestamptz,
  UNIQUE (nombre, institucion_id)
);

CREATE TABLE IF NOT EXISTS documentos (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  categoria_id bigint REFERENCES categorias(id),
  codigo_documento text UNIQUE,
  titulo text NOT NULL,
  descripcion text,
  activo boolean NOT NULL DEFAULT true,
  fecha_creacion timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  institucion_id bigint NOT NULL REFERENCES instituciones(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS documento_versiones (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  documento_id bigint NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
  numero_version integer NOT NULL DEFAULT 1,
  ruta_archivo text NOT NULL,
  storage_bucket text NOT NULL DEFAULT 'documents',
  original_filename text,
  mime_type text NOT NULL DEFAULT 'application/pdf',
  file_size_bytes bigint,
  status text NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING', 'PROCESSING', 'READY', 'FAILED')),
  es_version_activa boolean NOT NULL DEFAULT true,
  texto_extraido text,
  total_chunks integer NOT NULL DEFAULT 0,
  embedding_model text,
  indexed_at timestamptz,
  error_message text,
  fecha_carga timestamptz NOT NULL DEFAULT now(),
  cargado_por_external_auth_id text REFERENCES app_users(external_auth_id),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_chunks (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  documento_version_id bigint NOT NULL REFERENCES documento_versiones(id) ON DELETE CASCADE,
  chunk_index integer NOT NULL,
  page_number integer,
  chunk_text text NOT NULL,
  token_count integer,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_embeddings (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  chunk_id bigint NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
  embedding vector(1536) NOT NULL,
  embedding_model text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversaciones (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  external_auth_id text NOT NULL REFERENCES app_users(external_auth_id) ON DELETE CASCADE,
  title text NOT NULL,
  hidden boolean NOT NULL DEFAULT false,
  last_interaction timestamptz,
  fecha_creacion timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  institucion_id bigint NOT NULL REFERENCES instituciones(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mensajes (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  conversacion_id bigint NOT NULL REFERENCES conversaciones(id) ON DELETE CASCADE,
  external_auth_id text REFERENCES app_users(external_auth_id) ON DELETE SET NULL,
  rol_mensaje text NOT NULL CHECK (rol_mensaje IN ('USER', 'ASSISTANT')),
  contenido_texto text NOT NULL,
  proveedor_ia text,
  modelo_ia text,
  temperatura numeric,
  tokens_input integer,
  tokens_output integer,
  tiempo_respuesta_ms integer,
  audit_id uuid,
  fecha_envio timestamptz NOT NULL DEFAULT now(),
  contenido_anonimizado text
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversacion_id bigint REFERENCES conversaciones(id) ON DELETE SET NULL,
  mensaje_id bigint,
  external_auth_id text REFERENCES app_users(external_auth_id) ON DELETE SET NULL,
  pregunta_original text,
  pregunta_anonimizada text,
  respuesta_texto text,
  proveedor_ia text,
  modelo_ia text,
  embedding_model text,
  tokens_input integer,
  tokens_output integer,
  tiempo_respuesta_ms integer,
  score_fidelidad numeric,
  score_relevancia numeric,
  score_contexto numeric,
  observaciones text,
  fecha_evaluacion timestamptz NOT NULL DEFAULT now(),
  institucion_id bigint REFERENCES instituciones(id) ON DELETE SET NULL
);

ALTER TABLE mensajes
  ADD CONSTRAINT mensajes_audit_id_fkey FOREIGN KEY (audit_id)
  REFERENCES audit_logs(id) ON DELETE SET NULL;
ALTER TABLE audit_logs
  ADD CONSTRAINT audit_logs_mensaje_id_fkey FOREIGN KEY (mensaje_id)
  REFERENCES mensajes(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS message_documents (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  mensaje_id bigint NOT NULL REFERENCES mensajes(id) ON DELETE CASCADE,
  audit_id uuid REFERENCES audit_logs(id) ON DELETE CASCADE,
  documento_id bigint REFERENCES documentos(id) ON DELETE SET NULL,
  documento_version_id bigint REFERENCES documento_versiones(id) ON DELETE SET NULL,
  chunk_id bigint REFERENCES document_chunks(id) ON DELETE SET NULL,
  similarity_score double precision,
  page_number integer,
  fecha_creacion timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS feedback (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  message_id bigint NOT NULL REFERENCES mensajes(id) ON DELETE CASCADE,
  audit_id uuid REFERENCES audit_logs(id) ON DELETE SET NULL,
  external_auth_id text REFERENCES app_users(external_auth_id) ON DELETE SET NULL,
  rating integer NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment text,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  institucion_id bigint REFERENCES instituciones(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS audio_interactions (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  conversacion_id bigint REFERENCES conversaciones(id) ON DELETE SET NULL,
  mensaje_id bigint REFERENCES mensajes(id) ON DELETE SET NULL,
  external_auth_id text REFERENCES app_users(external_auth_id) ON DELETE SET NULL,
  ruta_audio_original text,
  ruta_audio_respuesta text,
  transcripcion text,
  transcription_model text,
  duracion_segundos numeric,
  formato_audio text,
  tamano_bytes bigint,
  fecha_creacion timestamptz NOT NULL DEFAULT now(),
  institucion_id bigint REFERENCES instituciones(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS pii_mappings (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  audit_id uuid REFERENCES audit_logs(id) ON DELETE CASCADE,
  external_auth_id text REFERENCES app_users(external_auth_id) ON DELETE SET NULL,
  token text NOT NULL,
  pii_type text NOT NULL,
  original_value text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  institucion_id bigint REFERENCES instituciones(id) ON DELETE SET NULL,
  expires_at timestamptz
);

CREATE TABLE IF NOT EXISTS suscripciones (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint NOT NULL REFERENCES instituciones(id) ON DELETE CASCADE,
  plan_id bigint NOT NULL REFERENCES planes(id) ON DELETE SET NULL,
  estado text NOT NULL DEFAULT 'TRIAL'
    CHECK (estado IN ('TRIAL', 'ACTIVE', 'PENDING_PAYMENT', 'SUSPENDED', 'CANCELLED', 'EXPIRED')),
  fecha_inicio timestamptz,
  fecha_vencimiento timestamptz,
  fecha_cancelacion timestamptz,
  cancelacion_programada boolean NOT NULL DEFAULT false,
  stripe_subscription_id text UNIQUE,
  stripe_customer_id text,
  auto_renovacion boolean NOT NULL DEFAULT true,
  periodo_prueba_inicio timestamptz,
  periodo_prueba_fin timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  stripe_price_id text,
  periodo_actual_inicio timestamptz,
  periodo_actual_fin timestamptz
);

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

CREATE TABLE IF NOT EXISTS pagos (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint NOT NULL REFERENCES instituciones(id) ON DELETE CASCADE,
  suscripcion_id bigint REFERENCES suscripciones(id) ON DELETE SET NULL,
  importe numeric NOT NULL DEFAULT 0 CHECK (importe >= 0),
  moneda character(3) DEFAULT 'USD',
  estado text NOT NULL DEFAULT 'PENDING'
    CHECK (estado IN ('PENDING', 'COMPLETED', 'FAILED', 'REFUNDED')),
  proveedor text,
  stripe_payment_intent_id text UNIQUE,
  stripe_checkout_session_id text UNIQUE,
  stripe_charge_id text,
  idempotency_key text UNIQUE,
  descripcion text,
  fecha_pago timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  stripe_invoice_id text
);

CREATE TABLE IF NOT EXISTS comprobantes (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint NOT NULL REFERENCES instituciones(id) ON DELETE CASCADE,
  pago_id bigint REFERENCES pagos(id) ON DELETE SET NULL,
  tipo_comprobante text NOT NULL,
  numero text,
  estado text NOT NULL DEFAULT 'PENDING'
    CHECK (estado IN ('PENDING', 'COMPLETED', 'FAILED', 'REFUNDED')),
  importe numeric,
  moneda character(3) DEFAULT 'USD',
  archivo_path text,
  proveedor text,
  referencia_externa text,
  fecha_emision timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stripe_eventos (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  stripe_event_id text UNIQUE NOT NULL,
  tipo_evento text NOT NULL,
  payload jsonb DEFAULT '{}'::jsonb,
  procesado boolean NOT NULL DEFAULT false,
  procesado_at timestamptz,
  error text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notificaciones (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint REFERENCES instituciones(id) ON DELETE CASCADE,
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
  created_at timestamptz NOT NULL DEFAULT now(),
  datos jsonb DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS configuracion_smtp (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint UNIQUE REFERENCES instituciones(id) ON DELETE CASCADE,
  servidor text,
  puerto integer DEFAULT 587,
  cifrado text DEFAULT 'STARTTLS'
    CHECK (cifrado IN ('NONE', 'SSL', 'TLS', 'STARTTLS')),
  usuario text,
  password_secret_ref text,
  correo_remitente text,
  nombre_remitente text,
  timeout_segundos integer NOT NULL DEFAULT 30,
  activo boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS plantillas_email (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint REFERENCES instituciones(id) ON DELETE CASCADE,
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

CREATE TABLE IF NOT EXISTS config_parametros (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint REFERENCES instituciones(id) ON DELETE CASCADE,
  clave text NOT NULL,
  valor text NOT NULL,
  tipo text NOT NULL DEFAULT 'string',
  descripcion text,
  editable_desde_dashboard boolean NOT NULL DEFAULT true,
  activo boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (institucion_id, clave)
);

CREATE TABLE IF NOT EXISTS solicitudes_acceso (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_nombre text NOT NULL,
  persona_contacto text NOT NULL,
  email text NOT NULL,
  telefono text,
  cantidad_usuarios_estimada integer,
  perfil_solicitado text,
  mensaje text,
  estado text NOT NULL DEFAULT 'PENDIENTE'
    CHECK (estado IN ('PENDIENTE', 'CONTACTADA', 'APROBADA', 'RECHAZADA')),
  origen text NOT NULL DEFAULT 'landing',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT solicitudes_acceso_cantidad_usuarios_check
    CHECK (cantidad_usuarios_estimada IS NULL OR cantidad_usuarios_estimada > 0)
);

CREATE INDEX IF NOT EXISTS idx_institucion_miembros_external_auth_id
  ON institucion_miembros (external_auth_id);
CREATE INDEX IF NOT EXISTS idx_institucion_miembros_institucion_id
  ON institucion_miembros (institucion_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_institucion_miembros_unica_activa
  ON institucion_miembros (external_auth_id) WHERE activo = true;
CREATE INDEX IF NOT EXISTS idx_categorias_institucion_id ON categorias (institucion_id);
CREATE INDEX IF NOT EXISTS idx_documentos_institucion_id ON documentos (institucion_id);
CREATE INDEX IF NOT EXISTS idx_conversaciones_institucion_id ON conversaciones (institucion_id);
CREATE INDEX IF NOT EXISTS idx_conversaciones_external_auth_id ON conversaciones (external_auth_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_institucion_id ON audit_logs (institucion_id);
CREATE INDEX IF NOT EXISTS idx_feedback_institucion_id ON feedback (institucion_id);
CREATE INDEX IF NOT EXISTS idx_audio_interactions_institucion_id ON audio_interactions (institucion_id);
CREATE INDEX IF NOT EXISTS idx_pii_mappings_institucion_id ON pii_mappings (institucion_id);
CREATE INDEX IF NOT EXISTS idx_pii_mappings_user_audit ON pii_mappings (external_auth_id, audit_id);
CREATE INDEX IF NOT EXISTS idx_config_parametros_clave ON config_parametros (clave);
CREATE INDEX IF NOT EXISTS idx_config_parametros_institucion_id ON config_parametros (institucion_id);
CREATE INDEX IF NOT EXISTS idx_solicitudes_acceso_estado ON solicitudes_acceso (estado);

CREATE OR REPLACE FUNCTION match_document_chunks (
  query_embedding vector(1536),
  match_count int default 5,
  similarity_threshold float default 0.0,
  p_institucion_id bigint default null
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
    dc.id AS chunk_id,
    d.id AS document_id,
    dv.id AS document_version_id,
    d.titulo AS document_title,
    dc.page_number,
    dc.chunk_text,
    1 - (de.embedding <=> query_embedding) AS similarity
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

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION match_document_chunks(vector, int, float, bigint)
  TO anon, authenticated, service_role;

INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion)
VALUES
  (NULL, 'llm_enabled', 'false', 'bool', 'LLM desactivado en prueba local'),
  (NULL, 'llm_model', 'openai/gpt-oss-20b', 'string', 'Modelo LLM para generación (override institucional)'),
  (NULL, 'judge_enabled', 'false', 'bool', 'Juez desactivado en prueba local'),
  (NULL, 'judge_model', 'openai/gpt-4o-mini', 'string', 'Modelo LLM para el juez (override institucional)'),
  (NULL, 'embeddings_enabled', 'false', 'bool', 'Embeddings desactivados en prueba local'),
  (NULL, 'pii_anonymization_enabled', 'false', 'bool', 'PII desactivada en prueba local'),
  (NULL, 'handoff_enabled', 'false', 'bool', 'Handoff desactivado en prueba local'),
  (NULL, 'pii_mapping_retention_days', '90', 'int', 'Retención de mappings PII')
ON CONFLICT (institucion_id, clave) DO NOTHING;
