-- Migración 014 — Modelo LLM configurable por institución
-- Inserta los defaults globales; cada institución puede crear su override
-- (precedencia institucional > global > settings/.env).
-- `llm_model` se usa para generar respuestas; `judge_model` para LLM-as-a-Judge.

INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion, editable_desde_dashboard, activo)
SELECT NULL, 'llm_model', 'openai/gpt-4o-mini', 'string',
       'Modelo LLM para generación de respuestas (override institucional permitido)',
       TRUE, TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM config_parametros
  WHERE clave = 'llm_model' AND institucion_id IS NULL
);

INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion, editable_desde_dashboard, activo)
SELECT NULL, 'judge_model', 'openai/gpt-4o-mini', 'string',
       'Modelo LLM para evaluación automática de calidad (override institucional permitido)',
       TRUE, TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM config_parametros
  WHERE clave = 'judge_model' AND institucion_id IS NULL
);
