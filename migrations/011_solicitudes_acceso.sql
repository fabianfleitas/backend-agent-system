-- 011_solicitudes_acceso.sql
-- Solicitudes de acceso enviadas desde el formulario público /solicitar-acceso.
-- No tiene FK a instituciones: la institución todavía no existe cuando se solicita.

CREATE TABLE IF NOT EXISTS public.solicitudes_acceso (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  institucion_nombre text NOT NULL,
  persona_contacto text NOT NULL,
  email text NOT NULL,
  telefono text,
  cantidad_usuarios_estimada integer,
  perfil_solicitado text,
  mensaje text,
  estado text NOT NULL DEFAULT 'PENDIENTE'::text,
  origen text NOT NULL DEFAULT 'landing'::text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT solicitudes_acceso_pkey PRIMARY KEY (id),
  CONSTRAINT solicitudes_acceso_estado_check CHECK (
    estado = ANY (ARRAY[
      'PENDIENTE'::text,
      'CONTACTADA'::text,
      'APROBADA'::text,
      'RECHAZADA'::text
    ])
  ),
  CONSTRAINT solicitudes_acceso_cantidad_usuarios_check CHECK (
    cantidad_usuarios_estimada IS NULL OR cantidad_usuarios_estimada > 0
  )
);

CREATE INDEX IF NOT EXISTS idx_solicitudes_acceso_estado
  ON public.solicitudes_acceso (estado, created_at DESC);
