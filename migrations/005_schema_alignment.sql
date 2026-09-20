-- Migrations 005_schema_alignment.sql
-- Alinea DB real (exportada Aug 2026) con los pendientes y corrige inconsistencias
-- de defaults vs CHECK constraints. Aplicar con psql / Supabase SQL Editor.

-- ============================================
-- A. OBLIGATORIO — defaults que violaban CHECK
-- ============================================

-- A1. comprobantes.estado default 'GENERADO' no está en CHECK
--     (PENDING, COMPLETED, FAILED, REFUNDED)
ALTER TABLE comprobantes ALTER COLUMN estado SET DEFAULT 'PENDING';

-- A2. suscripciones.estado default 'PENDING' no está en CHECK
--     (TRIAL, ACTIVE, PENDING_PAYMENT, SUSPENDED, CANCELLED, EXPIRED)
ALTER TABLE suscripciones ALTER COLUMN estado SET DEFAULT 'TRIAL';

-- A3. Índice faltante en suscripcion_historial (ya se escribe en billing_repository)
CREATE INDEX IF NOT EXISTS idx_suscripcion_historial_suscripcion_id
  ON suscripcion_historial (suscripcion_id);

-- ============================================
-- B. OPCIONAL — según bloques pendientes
-- ============================================

# APLICADO — 2026-08-29
# B1 (pii_mappings.expires_at) aplicado por decision de fase futura (§5)
-- ALTER TABLE pii_mappings ADD COLUMN IF NOT EXISTS expires_at timestamptz;
-- CREATE INDEX IF NOT EXISTS idx_pii_mappings_user_audit ON pii_mappings (external_auth_id, audit_id);

# APLICADO — 2026-08-29
# B2 (notificaciones.datos) aplicado para variables plantilla (§11)
-- ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS datos jsonb DEFAULT '{}';

# APLICADO — 2026-08-29
# B3 (categorias orden/fecha_baja) aplicado para CRUD (§14)
-- Si haces CRUD completo con categorías globales (institucion_id IS NULL),
-- UNIQUE(nombre, institucion_id) no protege duplicados globales porque NULL
-- no compara igual. Índice parcial opcional:
-- CREATE UNIQUE INDEX IF NOT EXISTS uq_categorias_global_nombre
--   ON categorias (lower(nombre)) WHERE institucion_id IS NULL;
-- Opcional soft-delete / orden:
-- ALTER TABLE categorias ADD COLUMN IF NOT EXISTS orden int DEFAULT 0;
-- ALTER TABLE categorias ADD COLUMN IF NOT EXISTS fecha_baja timestamptz;

-- ============================================
-- C. APLICADO — alinear tipo_miembro (DB text default 'STUDENT' vs código 'ESTUDIANTE');
-- FIX CHECK + backfill aplicados vía 006_schema_alignment.sql (2026-08-29)
-- ============================================
-- El código y schemas/admin.py usan "ESTUDIANTE"; la DB usaba 'STUDENT'.
-- CHECK corregido para permitir ADMIN/SECRETARIA/ESTUDIANTE/STUDENT.
