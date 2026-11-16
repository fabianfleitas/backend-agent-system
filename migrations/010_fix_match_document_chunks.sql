-- Migración 010 — Fix: función match_document_chunks devolvía siempre vacío
-- Síntoma: RAG no recuperaba contexto (run_eval → retrieval_accuracy 0) aunque
-- existían documentos READY + embeddings, incluso con similarity_threshold <= 0.
-- Causas: (1) definición desplegada quedó rota; (2) se generaron overloads con
-- distinto orden de parámetros → PGRST203.
-- Fix: elimina cualquier overload de match_document_chunks y recrea una única
-- función (params con default para cumplir regla 42P13) + search_path explícito.

SET search_path = public;

DROP FUNCTION IF EXISTS match_document_chunks(vector, integer, double precision, bigint);
DROP FUNCTION IF EXISTS match_document_chunks(vector, bigint, integer, double precision);

CREATE OR REPLACE FUNCTION match_document_chunks (
  query_embedding vector(1536),
  match_count int default 5,
  similarity_threshold float default 0.0,
  p_institucion_id bigint default null
)
RETURNS table (
  chunk_id bigint,
  document_id bigint,
  document_version_id bigint,
  document_title text,
  page_number int,
  chunk_text text,
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    dc.id as chunk_id,
    d.id as document_id,
    dv.id as document_version_id,
    d.titulo as document_title,
    dc.page_number,
    dc.chunk_text,
    1 - (de.embedding <=> query_embedding) as similarity
  FROM document_embeddings de
  JOIN document_chunks dc ON dc.id = de.chunk_id
  JOIN documento_versiones dv ON dv.id = dc.documento_version_id
  JOIN documentos d ON d.id = dv.documento_id
  WHERE
    d.activo = true
    AND dv.status = 'READY'
    AND dv.es_version_activa = true
    AND d.institucion_id = p_institucion_id
    AND (1 - (de.embedding <=> query_embedding)) >= similarity_threshold
  ORDER BY de.embedding <=> query_embedding
  LIMIT match_count;
$$;

-- Verificación:
-- SELECT chunk_id, document_title, round(similarity::numeric, 3) AS sim
-- FROM match_document_chunks((SELECT embedding FROM document_embeddings LIMIT 1), 5, 0.0, 1);