tables.sql

create extension if not exists vector;
create extension if not exists pgcrypto;

--enums

create type user_role as enum ('STUDENT', 'STAFF', 'ADMIN');

create type document_status as enum (
  'PENDING',
  'PROCESSING',
  'READY',
  'FAILED'
);

create type message_sender as enum (
  'USER',
  'ASSISTANT',
  'SYSTEM'
);

create type message_role as enum ('USER', 'ASSISTANT', 'SYSTEM');


create type document_visibility as enum (
  'PUBLIC',
  'INTERNAL'
);

--users

create table if not exists app_users (
  id bigint generated always as identity primary key,
  external_auth_id text not null unique,
  email text not null,
  full_name text,
  role user_role not null default 'STUDENT',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

--categorias

create table if not exists categorias (
  id bigint generated always as identity primary key,
  nombre text not null unique,
  descripcion text,
  activo boolean not null default true,
  fecha_creacion timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

--documentos

create table if not exists documentos (
  id bigint generated always as identity primary key,
  categoria_id bigint references categorias(id) on delete set null,
  codigo_documento text unique,
  titulo text not null,
  descripcion text,
  activo boolean not null default true,
  fecha_creacion timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

--versiones de documentso

create table if not exists documento_versiones (
  id bigint generated always as identity primary key,
  documento_id bigint not null references documentos(id) on delete cascade,
  numero_version int not null default 1,
  ruta_archivo text not null,
  storage_bucket text not null default 'documents',
  original_filename text,
  mime_type text not null default 'application/pdf',
  file_size_bytes bigint,
  status document_status not null default 'PENDING',
  es_version_activa boolean not null default true,
  texto_extraido text,
  total_chunks int not null default 0,
  embedding_model text,
  indexed_at timestamptz,
  error_message text,
  fecha_carga timestamptz not null default now(),
  cargado_por_external_auth_id text references app_users(external_auth_id) on delete set null,

  unique(documento_id, numero_version)
);

--chuncks documentos

create table if not exists document_chunks (
  id bigint generated always as identity primary key,
  documento_version_id bigint not null references documento_versiones(id) on delete cascade,
  chunk_index int not null,
  page_number int,
  chunk_text text not null,
  token_count int,
  created_at timestamptz not null default now(),

  unique(documento_version_id, chunk_index)
);

--emnbedings pg vector
create table if not exists document_embeddings (
  id bigint generated always as identity primary key,
  chunk_id bigint not null references document_chunks(id) on delete cascade,
  embedding vector(1536) not null,
  embedding_model text not null,
  created_at timestamptz not null default now(),

  unique(chunk_id, embedding_model)
);

--indice vectorial

create index if not exists idx_document_embeddings_vector
on document_embeddings
using hnsw (embedding vector_cosine_ops);

--conversaciones

create table if not exists conversaciones (
  id bigint generated always as identity primary key,
  external_auth_id text not null references app_users(external_auth_id) on delete cascade,
  title text not null,
  hidden boolean not null default false,
  last_interaction timestamptz,
  fecha_creacion timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

--mensajes

create table if not exists mensajes (
  id bigint generated always as identity primary key,
  conversacion_id bigint not null references conversaciones(id) on delete cascade,
  external_auth_id text references app_users(external_auth_id) on delete set null,
  rol_mensaje message_role not null,
  contenido_texto text not null,

  proveedor_ia text,
  modelo_ia text,
  temperatura numeric(4,2),
  tokens_input int,
  tokens_output int,
  tiempo_respuesta_ms int,

  audit_id uuid,
  fecha_envio timestamptz not null default now()
);

--auditoria

create table if not exists audit_logs (
  id uuid primary key default gen_random_uuid(),

  conversacion_id bigint references conversaciones(id) on delete set null,
  mensaje_id bigint references mensajes(id) on delete set null,
  external_auth_id text references app_users(external_auth_id) on delete set null,

  pregunta_original text,
  pregunta_anonimizada text,
  respuesta_texto text,

  proveedor_ia text,
  modelo_ia text,
  embedding_model text,

  tokens_input int,
  tokens_output int,
  tiempo_respuesta_ms int,

  score_fidelidad numeric(5,2),
  score_relevancia numeric(5,2),
  score_contexto numeric(5,2),
  observaciones text,

  fecha_evaluacion timestamptz not null default now()
);

--fk mensajes auditoria

do $$
begin
  alter table mensajes
  add constraint mensajes_audit_id_fkey
  foreign key (audit_id) references audit_logs(id)
  on delete set null;
exception
  when duplicate_object then null;
end $$;

--Trazabilidad RAG: mensaje-documentos

create table if not exists message_documents (
  id bigint generated always as identity primary key,

  mensaje_id bigint not null references mensajes(id) on delete cascade,
  audit_id uuid references audit_logs(id) on delete cascade,

  documento_id bigint references documentos(id) on delete set null,
  documento_version_id bigint references documento_versiones(id) on delete set null,
  chunk_id bigint references document_chunks(id) on delete set null,

  similarity_score float,
  page_number int,

  fecha_creacion timestamptz not null default now()
);

--Feedback

create table if not exists feedback (
  id bigint generated always as identity primary key,

  message_id bigint not null references mensajes(id) on delete cascade,
  audit_id uuid references audit_logs(id) on delete cascade,
  external_auth_id text references app_users(external_auth_id) on delete set null,

  rating int not null check (rating between 1 and 5),
  comment text,

  created_at timestamptz not null default now()
);

--Audio interactions

create table if not exists audio_interactions (
  id bigint generated always as identity primary key,

  conversacion_id bigint references conversaciones(id) on delete cascade,
  mensaje_id bigint references mensajes(id) on delete set null,
  external_auth_id text references app_users(external_auth_id) on delete set null,

  ruta_audio_original text,
  ruta_audio_respuesta text,

  transcripcion text,
  transcription_model text,

  duracion_segundos numeric(10,2),
  formato_audio text,
  tamano_bytes bigint,

  fecha_creacion timestamptz not null default now()
);

--Mapeo PII

create table if not exists pii_mappings (
  id bigint generated always as identity primary key,

  audit_id uuid references audit_logs(id) on delete cascade,
  external_auth_id text references app_users(external_auth_id) on delete set null,

  token text not null,
  pii_type text not null,
  original_value text not null,

  created_at timestamptz not null default now()
);

--Función de búsqueda semántica

create or replace function match_document_chunks (
  query_embedding vector(1536),
  match_count int default 5,
  similarity_threshold float default 0.0
)
returns table (
  chunk_id bigint,
  document_id bigint,
  document_version_id bigint,
  document_title text,
  page_number int,
  chunk_text text,
  similarity float
)
language sql stable
as $$
  select
    dc.id as chunk_id,
    d.id as document_id,
    dv.id as document_version_id,
    d.titulo as document_title,
    dc.page_number,
    dc.chunk_text,
    1 - (de.embedding <=> query_embedding) as similarity
  from document_embeddings de
  join document_chunks dc on dc.id = de.chunk_id
  join documento_versiones dv on dv.id = dc.documento_version_id
  join documentos d on d.id = dv.documento_id
  where
    d.activo = true
    and dv.status = 'READY'
    and (1 - (de.embedding <=> query_embedding)) >= similarity_threshold
  order by de.embedding <=> query_embedding
  limit match_count;
$$;

--Índices

create index if not exists idx_app_users_external_auth_id
on app_users(external_auth_id);

create index if not exists idx_app_users_role
on app_users(role);

create index if not exists idx_conversaciones_external_auth_id
on conversaciones(external_auth_id);

create index if not exists idx_conversaciones_last_interaction
on conversaciones(last_interaction desc);

create index if not exists idx_mensajes_conversacion_id
on mensajes(conversacion_id);

create index if not exists idx_mensajes_audit_id
on mensajes(audit_id);

create index if not exists idx_documentos_categoria_id
on documentos(categoria_id);

create index if not exists idx_documento_versiones_documento_id
on documento_versiones(documento_id);

create index if not exists idx_document_chunks_version_id
on document_chunks(documento_version_id);

create index if not exists idx_audit_logs_external_auth_id
on audit_logs(external_auth_id);

create index if not exists idx_audit_logs_fecha
on audit_logs(fecha_evaluacion desc);

create index if not exists idx_feedback_audit_id
on feedback(audit_id);

create index if not exists idx_message_documents_mensaje_id
on message_documents(mensaje_id);

create index if not exists idx_message_documents_audit_id
on message_documents(audit_id);

--Trigger updated_at

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_app_users_updated_at on app_users;
create trigger trg_app_users_updated_at
before update on app_users
for each row execute function set_updated_at();

drop trigger if exists trg_categorias_updated_at on categorias;
create trigger trg_categorias_updated_at
before update on categorias
for each row execute function set_updated_at();

drop trigger if exists trg_documentos_updated_at on documentos;
create trigger trg_documentos_updated_at
before update on documentos
for each row execute function set_updated_at();

drop trigger if exists trg_documento_versiones_updated_at on documento_versiones;
create trigger trg_documento_versiones_updated_at
before update on documento_versiones
for each row execute function set_updated_at();

drop trigger if exists trg_conversaciones_updated_at on conversaciones;
create trigger trg_conversaciones_updated_at
before update on conversaciones
for each row execute function set_updated_at();

-- storage storage.buckets
insert into storage.buckets (
  id,
  name,
  public,
  file_size_limit,
  allowed_mime_types
)
values (
  'documents',
  'documents',
  false,
  52428800,
  array['application/pdf']
)
on conflict (id) do nothing;
--audio
insert into storage.buckets (
  id,
  name,
  public,
  file_size_limit,
  allowed_mime_types
)
values (
  'audio',
  'audio',
  false,
  52428800,
  array[
    'audio/wav',
    'audio/mpeg',
    'audio/webm',
    'audio/ogg',
    'audio/mp4'
  ]
)
on conflict (id) do nothing;


-- Datos semilla

insert into categorias (nombre, descripcion)
values
  ('Matriculación', 'Documentos relacionados al proceso de matrícula'),
  ('Aranceles', 'Documentos relacionados a costos, cuotas y pagos'),
  ('Becas', 'Documentos relacionados a becas y beneficios'),
  ('Calendario Académico', 'Fechas importantes del calendario institucional')
on conflict (nombre) do nothing;

--Usuarios mock

insert into app_users (
  external_auth_id,
  email,
  full_name,
  role
)
values
  ('mock-student', 'student@tesis.local', 'Alumno Demo', 'STUDENT'),
  ('mock-admin', 'admin@tesis.local', 'Administrador Demo', 'ADMIN'),
  ('mock-staff', 'staff@tesis.local', 'Secretaría Demo', 'STAFF')
on conflict (external_auth_id) do nothing;

--mock par aprobar fuentes

insert into documentos (
  categoria_id,
  codigo_documento,
  titulo,
  descripcion,
  activo
)
values (
  (select id from categorias where nombre = 'Matriculación' limit 1),
  'REG-001',
  'Reglamento Académico',
  'Documento institucional de prueba',
  true
)
on conflict (codigo_documento) do nothing;