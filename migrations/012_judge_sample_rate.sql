-- Migración 012 — Muestreo de LLM-as-a-Judge (RNF-05)
-- El juez no se ejecuta en el 100 % de las consultas interactivas.
--   0.0 = ninguna consulta (protege el SLO de latencia RNF-05)
--   1.0 = todas (solo corridas de evaluación A/B)
-- Precedencia: institucional > global > settings/.env (ConfigService).
--
-- Nota: al existir la fila global, el valor de BD tiene precedencia sobre
-- JUDGE_SAMPLE_RATE del .env. Para una corrida A/B, usar un override
-- institucional (institucion_id = X) con valor 1.0 y luego desactivarlo, o
-- actualizar temporalmente la fila global y restaurarla a 0.0.

INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion, editable_desde_dashboard, activo)
SELECT NULL, 'judge_sample_rate', '0.0', 'float',
       'Fracción de consultas evaluadas por LLM-as-a-Judge (0.0 ninguna; 1.0 todas). Mantener 0.0 en interactivo para RNF-05.',
       TRUE, TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM config_parametros
  WHERE clave = 'judge_sample_rate' AND institucion_id IS NULL
);
