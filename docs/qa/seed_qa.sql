-- Seed de QA para la verificación del índice parcial de membresía activa.
--
-- Verifica la política de la migración 004: un usuario no puede tener más de una
-- membresía institucional ACTIVA al mismo tiempo (índice parcial único
-- `uq_institucion_miembros_unica_activa` sobre `external_auth_id WHERE activo`).
--
-- Uso manual (SQL editor de Supabase o psql con rol service_role):
--   psql "$DATABASE_URL" -f docs/qa/seed_qa.sql
--
-- La prueba automatizada `tests/integration/test_cross_tenant_integration.py`
-- crea y elimina sus propios datos con identificadores únicos, por lo que este
-- seed es opcional y sirve para inspección o ejecución repetible con IDs fijos.
-- Para limpiar: docs/qa/cleanup_qa.sql

-- Usuario de prueba (perfil mínimo). El esquema real vive en all_tables.json.
INSERT INTO app_users (external_auth_id, email, full_name, is_active)
VALUES ('qa-miembro-unico', 'qa.miembro@ejemplo-test.edu', 'QA Miembro Único', true)
ON CONFLICT (external_auth_id) DO NOTHING;

-- Dos instituciones distintas para intentar dos membresías activas.
INSERT INTO instituciones (nombre, codigo)
VALUES
  ('QA Institución A', 'QA-INST-A'),
  ('QA Institución B', 'QA-INST-B')
ON CONFLICT (codigo) DO NOTHING;

-- Primera membresía activa (debe aceptarse).
INSERT INTO institucion_miembros (institucion_id, external_auth_id, tipo_miembro, activo)
SELECT i.id, 'qa-miembro-unico', 'ESTUDIANTE', true
FROM instituciones i
WHERE i.codigo = 'QA-INST-A'
  AND NOT EXISTS (
    SELECT 1 FROM institucion_miembros m
    WHERE m.external_auth_id = 'qa-miembro-unico' AND m.activo = true
  );

-- Segunda membresía activa en otra institución (DEBE fallar por el índice 004):
--   ERROR: duplicate key value violates unique constraint
--          "uq_institucion_miembros_unica_activa"
-- Descomentar solo para verificar manualmente el rechazo:
-- INSERT INTO institucion_miembros (institucion_id, external_auth_id, tipo_miembro, activo)
-- SELECT i.id, 'qa-miembro-unico', 'ESTUDIANTE', true
-- FROM instituciones i WHERE i.codigo = 'QA-INST-B';
