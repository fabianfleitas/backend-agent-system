-- Migración 015 — Cambio del modelo global de generación
-- El modelo se resuelve por institución (precedencia institucional > global >
-- settings/.env). Esta migración actualiza el default global a DeepSeek V4.1
-- Flash 1017 y lo crea si no existe. Los overrides institucionales existentes
-- no se modifican.

INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion, editable_desde_dashboard, activo)
SELECT NULL, 'llm_model', 'deepseek/deepseek-v4.1-flash-1017', 'string',
       'Modelo LLM para generación de respuestas (override institucional permitido)',
       TRUE, TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM config_parametros
  WHERE clave = 'llm_model' AND institucion_id IS NULL
);

UPDATE config_parametros
SET valor = 'deepseek/deepseek-v4.1-flash-1017', updated_at = now()
WHERE clave = 'llm_model' AND institucion_id IS NULL;
