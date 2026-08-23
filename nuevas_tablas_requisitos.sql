BEGIN;

-- ============================================================
-- 1. INSTITUCIONES
-- ============================================================

CREATE TABLE IF NOT EXISTS public.instituciones (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    nombre TEXT NOT NULL,
    nombre_comercial TEXT,
    codigo TEXT UNIQUE,

    email_contacto TEXT,
    telefono_contacto TEXT,

    direccion TEXT,
    ciudad TEXT,
    pais TEXT DEFAULT 'Paraguay',

    activo BOOLEAN NOT NULL DEFAULT TRUE,

    -- Stripe Customer asociado a la institución
    stripe_customer_id TEXT UNIQUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================
-- 2. RELACIÓN USUARIO <-> INSTITUCIÓN
-- ============================================================
-- No modificamos user_role.
-- Esto permite que un usuario pueda pertenecer a varias
-- instituciones en el futuro.

CREATE TABLE IF NOT EXISTS public.institucion_miembros (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    institucion_id BIGINT NOT NULL,
    external_auth_id TEXT NOT NULL,

    tipo_miembro TEXT NOT NULL DEFAULT 'STUDENT'
        CHECK (
            tipo_miembro IN (
                'STUDENT',
                'SECRETARIA',
                'ADMIN'
            )
        ),

    activo BOOLEAN NOT NULL DEFAULT TRUE,

    fecha_ingreso TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_salida TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT institucion_miembros_institucion_fk
        FOREIGN KEY (institucion_id)
        REFERENCES public.instituciones(id),

    CONSTRAINT institucion_miembros_usuario_fk
        FOREIGN KEY (external_auth_id)
        REFERENCES public.app_users(external_auth_id),

    CONSTRAINT institucion_miembros_unique
        UNIQUE (institucion_id, external_auth_id)
);


-- ============================================================
-- 3. AISLAMIENTO MULTIINSTITUCIÓN
-- ============================================================

ALTER TABLE public.categorias
ADD COLUMN IF NOT EXISTS institucion_id BIGINT;

ALTER TABLE public.documentos
ADD COLUMN IF NOT EXISTS institucion_id BIGINT;

ALTER TABLE public.conversaciones
ADD COLUMN IF NOT EXISTS institucion_id BIGINT;

ALTER TABLE public.audit_logs
ADD COLUMN IF NOT EXISTS institucion_id BIGINT;

ALTER TABLE public.feedback
ADD COLUMN IF NOT EXISTS institucion_id BIGINT;

ALTER TABLE public.audio_interactions
ADD COLUMN IF NOT EXISTS institucion_id BIGINT;

ALTER TABLE public.pii_mappings
ADD COLUMN IF NOT EXISTS institucion_id BIGINT;


-- ============================================================
-- 4. FOREIGN KEYS MULTIINSTITUCIÓN
-- ============================================================

DO $$
BEGIN

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'categorias_institucion_fk'
    ) THEN
        ALTER TABLE public.categorias
        ADD CONSTRAINT categorias_institucion_fk
        FOREIGN KEY (institucion_id)
        REFERENCES public.instituciones(id);
    END IF;


    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'documentos_institucion_fk'
    ) THEN
        ALTER TABLE public.documentos
        ADD CONSTRAINT documentos_institucion_fk
        FOREIGN KEY (institucion_id)
        REFERENCES public.instituciones(id);
    END IF;


    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'conversaciones_institucion_fk'
    ) THEN
        ALTER TABLE public.conversaciones
        ADD CONSTRAINT conversaciones_institucion_fk
        FOREIGN KEY (institucion_id)
        REFERENCES public.instituciones(id);
    END IF;


    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'audit_logs_institucion_fk'
    ) THEN
        ALTER TABLE public.audit_logs
        ADD CONSTRAINT audit_logs_institucion_fk
        FOREIGN KEY (institucion_id)
        REFERENCES public.instituciones(id);
    END IF;


    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'feedback_institucion_fk'
    ) THEN
        ALTER TABLE public.feedback
        ADD CONSTRAINT feedback_institucion_fk
        FOREIGN KEY (institucion_id)
        REFERENCES public.instituciones(id);
    END IF;


    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'audio_interactions_institucion_fk'
    ) THEN
        ALTER TABLE public.audio_interactions
        ADD CONSTRAINT audio_interactions_institucion_fk
        FOREIGN KEY (institucion_id)
        REFERENCES public.instituciones(id);
    END IF;


    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'pii_mappings_institucion_fk'
    ) THEN
        ALTER TABLE public.pii_mappings
        ADD CONSTRAINT pii_mappings_institucion_fk
        FOREIGN KEY (institucion_id)
        REFERENCES public.instituciones(id);
    END IF;

END $$;


-- ============================================================
-- 5. PLANES
-- ============================================================

CREATE TABLE IF NOT EXISTS public.planes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    codigo TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    descripcion TEXT,

    precio NUMERIC(12,2) NOT NULL DEFAULT 0
        CHECK (precio >= 0),

    moneda CHAR(3) NOT NULL DEFAULT 'USD',

    intervalo TEXT NOT NULL DEFAULT 'MONTH'
        CHECK (
            intervalo IN (
                'MONTH',
                'YEAR'
            )
        ),

    -- Límites principales del plan
    max_documentos INTEGER,
    max_usuarios INTEGER,
    max_estudiantes INTEGER,

    -- Permite agregar características sin modificar
    -- estructura de DB cada vez.
    features JSONB NOT NULL DEFAULT '{}'::jsonb,

    stripe_product_id TEXT UNIQUE,
    stripe_price_id TEXT UNIQUE,

    activo BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================
-- 6. SUSCRIPCIONES
-- ============================================================

CREATE TABLE IF NOT EXISTS public.suscripciones (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    institucion_id BIGINT NOT NULL,
    plan_id BIGINT NOT NULL,

    estado TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (
            estado IN (
                'PENDING',
                'TRIALING',
                'ACTIVE',
                'PAST_DUE',
                'PAUSED',
                'CANCELED',
                'EXPIRED',
                'INCOMPLETE'
            )
        ),

    fecha_inicio TIMESTAMPTZ,
    fecha_vencimiento TIMESTAMPTZ,

    fecha_cancelacion TIMESTAMPTZ,
    cancelacion_programada BOOLEAN NOT NULL DEFAULT FALSE,

    -- Stripe
    stripe_subscription_id TEXT UNIQUE,
    stripe_customer_id TEXT,

    auto_renovacion BOOLEAN NOT NULL DEFAULT TRUE,

    periodo_prueba_inicio TIMESTAMPTZ,
    periodo_prueba_fin TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT suscripciones_institucion_fk
        FOREIGN KEY (institucion_id)
        REFERENCES public.instituciones(id),

    CONSTRAINT suscripciones_plan_fk
        FOREIGN KEY (plan_id)
        REFERENCES public.planes(id)
);


-- ============================================================
-- 7. HISTORIAL DE SUSCRIPCIONES
-- ============================================================

CREATE TABLE IF NOT EXISTS public.suscripcion_historial (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    suscripcion_id BIGINT NOT NULL,

    tipo_evento TEXT NOT NULL
        CHECK (
            tipo_evento IN (
                'CREATED',
                'ACTIVATED',
                'RENEWED',
                'PLAN_CHANGED',
                'CANCELED',
                'EXPIRED',
                'PAUSED',
                'RESUMED',
                'PAYMENT_FAILED',
                'PAYMENT_SUCCEEDED'
            )
        ),

    plan_anterior_id BIGINT,
    plan_nuevo_id BIGINT,

    estado_anterior TEXT,
    estado_nuevo TEXT,

    descripcion TEXT,

    external_auth_id TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT suscripcion_historial_suscripcion_fk
        FOREIGN KEY (suscripcion_id)
        REFERENCES public.suscripciones(id),

    CONSTRAINT suscripcion_historial_plan_anterior_fk
        FOREIGN KEY (plan_anterior_id)
        REFERENCES public.planes(id),

    CONSTRAINT suscripcion_historial_plan_nuevo_fk
        FOREIGN KEY (plan_nuevo_id)
        REFERENCES public.planes(id),

    CONSTRAINT suscripcion_historial_usuario_fk
        FOREIGN KEY (external_auth_id)
        REFERENCES public.app_users(external_auth_id)
);


-- ============================================================
-- 8. PAGOS
-- ============================================================

CREATE TABLE IF NOT EXISTS public.pagos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    institucion_id BIGINT NOT NULL,
    suscripcion_id BIGINT,

    importe NUMERIC(12,2) NOT NULL
        CHECK (importe >= 0),

    moneda CHAR(3) NOT NULL DEFAULT 'USD',

    estado TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (
            estado IN (
                'PENDING',
                'PROCESSING',
                'APPROVED',
                'REJECTED',
                'CANCELED',
                'REFUNDED',
                'PARTIALLY_REFUNDED'
            )
        ),

    proveedor TEXT NOT NULL DEFAULT 'STRIPE',

    stripe_payment_intent_id TEXT UNIQUE,
    stripe_checkout_session_id TEXT UNIQUE,
    stripe_charge_id TEXT,

    -- Clave para evitar procesar dos veces una operación
    idempotency_key TEXT UNIQUE,

    descripcion TEXT,

    fecha_pago TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pagos_institucion_fk
        FOREIGN KEY (institucion_id)
        REFERENCES public.instituciones(id),

    CONSTRAINT pagos_suscripcion_fk
        FOREIGN KEY (suscripcion_id)
        REFERENCES public.suscripciones(id)
);


-- ============================================================
-- 9. EVENTOS STRIPE / WEBHOOKS
-- ============================================================
-- Fundamental para evitar procesar dos veces un webhook.

CREATE TABLE IF NOT EXISTS public.stripe_eventos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    stripe_event_id TEXT NOT NULL UNIQUE,

    tipo_evento TEXT NOT NULL,

    payload JSONB NOT NULL,

    procesado BOOLEAN NOT NULL DEFAULT FALSE,

    procesado_at TIMESTAMPTZ,

    error TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================
-- 10. COMPROBANTES
-- ============================================================

CREATE TABLE IF NOT EXISTS public.comprobantes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    institucion_id BIGINT NOT NULL,
    pago_id BIGINT,

    tipo_comprobante TEXT NOT NULL
        CHECK (
            tipo_comprobante IN (
                'CONFIRMACION_PAGO',
                'RECIBO',
                'FACTURA',
                'NOTA_CREDITO',
                'DEVOLUCION'
            )
        ),

    numero TEXT,

    estado TEXT NOT NULL DEFAULT 'GENERADO'
        CHECK (
            estado IN (
                'PENDIENTE',
                'GENERADO',
                'ANULADO'
            )
        ),

    importe NUMERIC(12,2),
    moneda CHAR(3) DEFAULT 'USD',

    archivo_path TEXT,

    proveedor TEXT,

    referencia_externa TEXT,

    fecha_emision TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT comprobantes_institucion_fk
        FOREIGN KEY (institucion_id)
        REFERENCES public.instituciones(id),

    CONSTRAINT comprobantes_pago_fk
        FOREIGN KEY (pago_id)
        REFERENCES public.pagos(id)
);


-- ============================================================
-- 11. NOTIFICACIONES
-- ============================================================

CREATE TABLE IF NOT EXISTS public.notificaciones (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    institucion_id BIGINT,
    suscripcion_id BIGINT,

    tipo TEXT NOT NULL
        CHECK (
            tipo IN (
                'SUBSCRIPTION_EXPIRING',
                'SUBSCRIPTION_EXPIRED',
                'PAYMENT_SUCCESS',
                'PAYMENT_FAILED',
                'PLAN_CHANGED',
                'SUBSCRIPTION_CANCELED',
                'SYSTEM'
            )
        ),

    canal TEXT NOT NULL
        CHECK (
            canal IN (
                'IN_APP',
                'EMAIL'
            )
        ),

    destinatario TEXT NOT NULL,

    asunto TEXT,
    contenido TEXT,

    estado TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (
            estado IN (
                'PENDING',
                'SENT',
                'FAILED',
                'CANCELED'
            )
        ),

    fecha_programada TIMESTAMPTZ,
    fecha_envio TIMESTAMPTZ,

    error TEXT,

    -- Permite evitar enviar dos veces
    clave_idempotencia TEXT UNIQUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT notificaciones_institucion_fk
        FOREIGN KEY (institucion_id)
        REFERENCES public.instituciones(id),

    CONSTRAINT notificaciones_suscripcion_fk
        FOREIGN KEY (suscripcion_id)
        REFERENCES public.suscripciones(id)
);


-- ============================================================
-- 12. CONFIGURACIÓN SMTP
-- ============================================================
-- IMPORTANTE:
-- NO guardar la contraseña directamente.
-- password_secret_ref debe apuntar a un secreto protegido.

CREATE TABLE IF NOT EXISTS public.configuracion_smtp (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    institucion_id BIGINT,

    servidor TEXT NOT NULL,
    puerto INTEGER NOT NULL DEFAULT 587,

    cifrado TEXT NOT NULL DEFAULT 'STARTTLS'
        CHECK (
            cifrado IN (
                'NONE',
                'SSL',
                'TLS',
                'STARTTLS'
            )
        ),

    usuario TEXT,

    password_secret_ref TEXT,

    correo_remitente TEXT NOT NULL,
    nombre_remitente TEXT,

    timeout_segundos INTEGER NOT NULL DEFAULT 30,

    activo BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT configuracion_smtp_institucion_fk
        FOREIGN KEY (institucion_id)
        REFERENCES public.instituciones(id)
);


-- ============================================================
-- 13. PLANTILLAS DE EMAIL
-- ============================================================

CREATE TABLE IF NOT EXISTS public.plantillas_email (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    institucion_id BIGINT,

    codigo TEXT NOT NULL,

    nombre TEXT NOT NULL,

    asunto TEXT NOT NULL,

    contenido_html TEXT NOT NULL,

    contenido_texto TEXT,

    activo BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT plantillas_email_institucion_fk
        FOREIGN KEY (institucion_id)
        REFERENCES public.instituciones(id),

    CONSTRAINT plantillas_email_unique
        UNIQUE (institucion_id, codigo)
);


-- ============================================================
-- 14. ÍNDICES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_institucion_miembros_institucion
ON public.institucion_miembros(institucion_id);

CREATE INDEX IF NOT EXISTS idx_institucion_miembros_usuario
ON public.institucion_miembros(external_auth_id);

CREATE INDEX IF NOT EXISTS idx_documentos_institucion
ON public.documentos(institucion_id);

CREATE INDEX IF NOT EXISTS idx_categorias_institucion
ON public.categorias(institucion_id);

CREATE INDEX IF NOT EXISTS idx_conversaciones_institucion
ON public.conversaciones(institucion_id);

CREATE INDEX IF NOT EXISTS idx_audit_logs_institucion
ON public.audit_logs(institucion_id);

CREATE INDEX IF NOT EXISTS idx_suscripciones_institucion
ON public.suscripciones(institucion_id);

CREATE INDEX IF NOT EXISTS idx_suscripciones_estado
ON public.suscripciones(estado);

CREATE INDEX IF NOT EXISTS idx_suscripciones_vencimiento
ON public.suscripciones(fecha_vencimiento);

CREATE INDEX IF NOT EXISTS idx_pagos_institucion
ON public.pagos(institucion_id);

CREATE INDEX IF NOT EXISTS idx_pagos_estado
ON public.pagos(estado);

CREATE INDEX IF NOT EXISTS idx_stripe_eventos_procesado
ON public.stripe_eventos(procesado);

CREATE INDEX IF NOT EXISTS idx_notificaciones_estado
ON public.notificaciones(estado);

CREATE INDEX IF NOT EXISTS idx_notificaciones_fecha_programada
ON public.notificaciones(fecha_programada);


-- ============================================================
-- 15. COMENTARIOS
-- ============================================================

COMMENT ON TABLE public.instituciones IS
'Instituciones clientes del sistema SaaS. Una instalación puede administrar múltiples instituciones.';

COMMENT ON TABLE public.planes IS
'Planes comerciales disponibles para las instituciones.';

COMMENT ON TABLE public.suscripciones IS
'Estado y ciclo de vida de la suscripción de una institución.';

COMMENT ON TABLE public.pagos IS
'Operaciones de pago procesadas mediante Stripe.';

COMMENT ON TABLE public.stripe_eventos IS
'Webhooks/eventos recibidos desde Stripe para garantizar idempotencia y trazabilidad.';

COMMENT ON TABLE public.comprobantes IS
'Registro de comprobantes y documentos derivados de operaciones de pago.';

COMMENT ON TABLE public.notificaciones IS
'Notificaciones internas y por correo relacionadas con suscripciones y pagos.';

COMMENT ON TABLE public.configuracion_smtp IS
'Configuración parametrizable del servicio de correo. Las credenciales deben almacenarse fuera de la base de datos o mediante referencia a secretos.';


COMMIT;
