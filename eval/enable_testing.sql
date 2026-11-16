-- =============================================================================
-- Habilitar todo para pruebas (S12) — SQL de configuración (idempotente)
-- -----------------------------------------------------------------------------
-- Habilita los flags que se leen desde config_parametros (DB): LLM, LLM-as-a-
-- Judge, PII y derivación a operador (handoff).
--
-- IMPORTANTE: NO habilita embeddings / STT / TTS (esos se leen del .env):
--   EMBEDDINGS_ENABLED=true, STT_ENABLED=true, TTS_ENABLED=true  (+ reiniciar
--   el backend).
--
-- Precedencia: si una institución tiene filas propias (institucion_id = X),
-- estas ganan sobre las globales (NULL). Usá la sección B por institución si
-- necesitás override.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- A) GLOBAL (aplica a todas las instituciones sin override propio)
-- -----------------------------------------------------------------------------
UPDATE config_parametros
SET valor = 'true', updated_at = now()
WHERE institucion_id IS NULL
  AND clave IN (
    'llm_enabled',
    'judge_enabled',
    'pii_anonymization_enabled',
    'handoff_enabled',
    'handoff_trigger_on_guard',
    'handoff_trigger_on_llm_failure'
  );

-- Detección de frustración (opcional)
UPDATE config_parametros
SET valor = 'true', updated_at = now()
WHERE institucion_id IS NULL AND clave = 'handoff_frustration_enabled';

-- Muestreo del juez al 100 % SOLO para evaluación (RNF-05 / A/B).
-- Restaurar a '0.0' al terminar las corridas.
UPDATE config_parametros
SET valor = '1.0', updated_at = now()
WHERE institucion_id IS NULL AND clave = 'judge_sample_rate';

-- -----------------------------------------------------------------------------
-- B) POR INSTITUCIÓN (opcional; reemplazar el 1 por el institucion_id real)
-- -----------------------------------------------------------------------------
-- INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion, editable_desde_dashboard, activo)
-- SELECT 1, k.clave, 'true', 'bool', k.descripcion, TRUE, TRUE
-- FROM (VALUES
--   ('llm_enabled', 'Activar LLM'),
--   ('judge_enabled', 'Activar LLM-as-a-Judge'),
--   ('handoff_enabled', 'Activar derivación a operador'),
--   ('handoff_trigger_on_guard', 'Escalar en guard'),
--   ('handoff_trigger_on_llm_failure', 'Escalar en fallo LLM'),
--   ('pii_anonymization_enabled', 'Activar anonimización PII')
-- ) AS k(clave, descripcion)
-- WHERE NOT EXISTS (
--   SELECT 1 FROM config_parametros c
--   WHERE c.institucion_id = 1 AND c.clave = k.clave
-- );

-- -----------------------------------------------------------------------------
-- C) VERIFICACIÓN
-- -----------------------------------------------------------------------------
SELECT institucion_id, clave, valor
FROM config_parametros
WHERE clave IN ('llm_enabled','judge_enabled','judge_sample_rate',
                'pii_anonymization_enabled','handoff_enabled',
                'handoff_trigger_on_guard','handoff_trigger_on_llm_failure')
ORDER BY clave, institucion_id NULLS FIRST;

-- Nota: ConfigService cachea 60 s. Si editas por SQL, espera <=60 s o reinicia
-- el backend; por el dashboard (PUT /api/admin/config/{clave}) invalida al instante.