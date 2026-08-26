-- Configuración operativa por institución (FASE F/H — tunable params, no secrets)
CREATE TABLE IF NOT EXISTS config_parametros (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  institucion_id bigint REFERENCES instituciones(id) ON DELETE CASCADE,
  clave text NOT NULL,
  valor text NOT NULL,
  tipo text NOT NULL DEFAULT 'string',
  descripcion text,
  editable_desde_dashboard boolean NOT NULL DEFAULT true,
  activo boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (institucion_id, clave)
);

CREATE INDEX IF NOT EXISTS idx_config_parametros_clave ON config_parametros(clave);
CREATE INDEX IF NOT EXISTS idx_config_parametros_institucion_id ON config_parametros(institucion_id);

-- Seed global defaults (institucion_id = NULL) con valores actuales del .env
INSERT INTO config_parametros (institucion_id, clave, valor, tipo, descripcion) VALUES
  (NULL, 'llm_model', 'openai/gpt-4o-mini', 'string', 'Modelo LLM via OpenRouter'),
  (NULL, 'llm_temperature', '0.2', 'float', 'Temperatura LLM'),
  (NULL, 'llm_max_tokens', '512', 'int', 'Max tokens respuesta'),
  (NULL, 'llm_history_enabled', 'true', 'bool', 'Incluir historial en prompt'),
  (NULL, 'llm_history_max_tokens', '1500', 'int', 'Token budget historial'),
  (NULL, 'llm_history_max_messages', '10', 'int', 'Mensajes previos en prompt'),
  (NULL, 'retrieval_similarity_threshold', '0.30', 'float', 'Umbral similitud RAG'),
  (NULL, 'retrieval_match_count', '5', 'int', 'Chunks recuperados'),
  (NULL, 'stt_enabled', 'false', 'bool', 'Feature flag STT'),
  (NULL, 'stt_model', 'x-ai/grok-stt-1.0', 'string', 'Modelo STT'),
  (NULL, 'tts_enabled', 'false', 'bool', 'Feature flag TTS'),
  (NULL, 'tts_model', 'hexgrad/kokoro-82m', 'string', 'Modelo TTS'),
  (NULL, 'tts_voice', 'ef_dora', 'string', 'Voz TTS'),
  (NULL, 'embedding_model', 'text-embedding-3-small', 'string', 'Modelo embeddings'),
  (NULL, 'embeddings_enabled', 'false', 'bool', 'Feature flag embeddings'),
  (NULL, 'llm_enabled', 'false', 'bool', 'Feature flag LLM');
