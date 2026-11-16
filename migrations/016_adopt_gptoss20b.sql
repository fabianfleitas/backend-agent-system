-- Migración 016 — Configuración definitiva de generación
-- Modelo adoptado: OpenAI GPT-OSS-20B, priorizando Groq en OpenRouter.
-- El enrutamiento de proveedor y el nivel de razonamiento se configuran por
-- entorno (.env): LLM_PROVIDER_ORDER=Groq, LLM_PROVIDER_ALLOW_FALLBACKS=false,
-- LLM_REASONING_EFFORT=low. La BD solo persiste el modelo por institución.

INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion, editable_desde_dashboard, activo)
SELECT NULL, 'llm_model', 'openai/gpt-oss-20b', 'string',
       'Modelo LLM para generación de respuestas (override institucional permitido)',
       TRUE, TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM config_parametros
  WHERE clave = 'llm_model' AND institucion_id IS NULL
);

UPDATE config_parametros
SET valor = 'openai/gpt-oss-20b', updated_at = now()
WHERE clave = 'llm_model' AND institucion_id IS NULL;
