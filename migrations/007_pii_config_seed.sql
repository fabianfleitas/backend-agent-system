-- PII / Anonimización (TODO §5) — configuración global y retención
-- NOTA: ON CONFLICT no cubre filas con institucion_id NULL (NULLs son distintos
-- para UNIQUE en Postgres); por eso se usa WHERE NOT EXISTS por fila.

INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion, editable_desde_dashboard, activo)
SELECT NULL, 'pii_anonymization_enabled', 'false', 'bool',
       'Anonimizar PII antes de enviar a proveedores externos (LLM/embeddings)',
       TRUE, TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM config_parametros WHERE clave = 'pii_anonymization_enabled' AND institucion_id IS NULL
);

INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion, editable_desde_dashboard, activo)
SELECT NULL, 'pii_mapping_retention_days', '90', 'int',
       'Días de retención de pii_mappings antes de purga (expires_at)',
       TRUE, TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM config_parametros WHERE clave = 'pii_mapping_retention_days' AND institucion_id IS NULL
);

-- Índice de trazabilidad usuario/auditoría para reidentificación interna y purga
CREATE INDEX IF NOT EXISTS idx_pii_mappings_user_audit ON pii_mappings (external_auth_id, audit_id);