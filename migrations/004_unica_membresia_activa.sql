-- 004_unica_membresia_activa.sql
-- Política: una institución activa por usuario. Resolver duplicados conservando la más reciente.

-- 1) Resolver duplicados: desactivar todas excepto la más reciente (fecha_ingreso DESC)
WITH ranked AS (
    SELECT id,
           row_number() OVER (PARTITION BY external_auth_id ORDER BY fecha_ingreso DESC, id DESC) AS rn
    FROM institucion_miembros
    WHERE activo = true
)
UPDATE institucion_miembros
SET activo = false,
    fecha_salida = now()
FROM ranked
WHERE institucion_miembros.id = ranked.id
  AND ranked.rn > 1;

-- 2) Defensa en profundidad: índice parcial único por usuario activo
CREATE UNIQUE INDEX IF NOT EXISTS uq_institucion_miembros_unica_activa
ON institucion_miembros (external_auth_id)
WHERE activo = true;
