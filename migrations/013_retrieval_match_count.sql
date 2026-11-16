-- Migración 013 — Ajuste de recuperación para latencia (RNF-05)
-- Reduce el número de fragmentos enviados al LLM (default 5 → 4).
-- Precedencia: institucional > global > settings/.env (ConfigService).
-- Re-medir RNF-05 después de aplicar; no afirmar cumplimiento sin la corrida.

INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion, editable_desde_dashboard, activo)
SELECT NULL, 'retrieval_match_count', '4', 'int',
       'Fragmentos recuperados por consulta (menos contexto = menor latencia). Ajuste RNF-05.',
       TRUE, TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM config_parametros
  WHERE clave = 'retrieval_match_count' AND institucion_id IS NULL
);
