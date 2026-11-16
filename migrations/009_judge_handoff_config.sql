-- Migración 009 — Configuración de LLM-as-a-Judge y derivación a operador
-- Habilita/deshabilita por institución (precedencia institucional > global).
-- No modifica tablas existentes: solo inserta parámetros globales (institucion_id NULL).

INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion, editable_desde_dashboard, activo)
SELECT NULL, 'judge_enabled', 'false', 'bool',
       'Evaluar cada respuesta generada por IA con LLM-as-a-Judge (fidelidad, relevancia, contexto)',
       TRUE, TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM config_parametros WHERE clave = 'judge_enabled' AND institucion_id IS NULL
);

INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion, editable_desde_dashboard, activo)
SELECT NULL, 'handoff_enabled', 'false', 'bool',
       'Habilitar derivación a operador humano (escalamiento vía notificaciones)',
       TRUE, TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM config_parametros WHERE clave = 'handoff_enabled' AND institucion_id IS NULL
);

INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion, editable_desde_dashboard, activo)
SELECT NULL, 'handoff_trigger_on_guard', 'true', 'bool',
       'Escalar cuando la consulta queda fuera del dominio (guard sin contexto)',
       TRUE, TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM config_parametros WHERE clave = 'handoff_trigger_on_guard' AND institucion_id IS NULL
);

INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion, editable_desde_dashboard, activo)
SELECT NULL, 'handoff_trigger_on_llm_failure', 'true', 'bool',
       'Escalar cuando la generación del LLM falla',
       TRUE, TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM config_parametros WHERE clave = 'handoff_trigger_on_llm_failure' AND institucion_id IS NULL
);

INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion, editable_desde_dashboard, activo)
SELECT NULL, 'handoff_frustration_enabled', 'false', 'bool',
       'Detectar frustración por heurística (palabras clave) para escalar',
       TRUE, TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM config_parametros WHERE clave = 'handoff_frustration_enabled' AND institucion_id IS NULL
);