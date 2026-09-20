-- Migrations 006 — Fix CHECK tipo_miembro + backfill (2026-08-29)
-- Corrige inconsistencia entre default 'ESTUDIANTE' (005/C) y CHECK que solo
-- permitía valores ingleses. Backfill de 'STUDENT' histórico a 'ESTUDIANTE'.

-- 1. Corregir CHECK (permite español + legado inglés)
ALTER TABLE institucion_miembros DROP CONSTRAINT IF EXISTS institucion_miembros_tipo_miembro_check;
ALTER TABLE institucion_miembros ADD CONSTRAINT institucion_miembros_tipo_miembro_check
  CHECK (tipo_miembro IN ('ADMIN', 'SECRETARIA', 'ESTUDIANTE', 'STUDENT'));

-- 2. Backfill histórico (2 filas en DB real; se aplica si existen)
UPDATE institucion_miembros SET tipo_miembro = 'ESTUDIANTE' WHERE tipo_miembro = 'STUDENT';
