# QA Manual — Multiinstitución A vs B

## Setup
- Aplicar `migrations/004_unica_membresia_activa.sql` (resuelve duplicados históricos).
- Cargar `docs/qa/seed_qa.sql` (2 instituciones + usuarios + membresías únicas + documento base).
- Uso de JWT de prueba (tokens de A: `qa-admin-a`; B: `qa-admin-b`).

## Checklist — Institución A
- [ ] Login / `/me` → `institucion_id=1`, `tipo_miembro=ADMIN`
- [ ] `/api/admin/documents` → solo documentos de A
- [ ] `/api/admin/documents/{B_doc}` con token A → 404
- [ ] `/api/chat/query` → contexto solo de A; no menciona B
- [ ] `/api/conversations` → solo conversaciones de A; ocultar conserva registro
- [ ] `/api/admin/audit` → solo eventos de A
- [ ] `/api/admin/config` → parámetros institucionales A + globales
- [ ] `/api/admin/categories` → categorías de A + globales
- [ ] `/api/admin/users` → solo usuarios miembros de A
- [ ] `/api/admin/metrics` → agregados solo de A
- [ ] `/api/admin/subscription`, `/admin/plan`, `/admin/pagos`, `/admin/comprobantes` → datos de A
- [ ] `/api/admin/stripe/checkout` (si hay credencial) → checkout asociado a A

## Checklist — Institución B
- [ ] Repetir inverso; confirmar 404 para todos los recursos de A.
- [ ] Confirmar que un usuario sin membresía no accede a `/admin/*`.
- [ ] Confirmar que `platform_admin` sin membresía institucional no pasa `/admin/*` (solo `/platform/*`).

## Criterio de cierre
- [ ] Ningún endpoint institucional expone datos de la otra institución.
- [ ] `get_document_by_id` con `institucion_id=2` y auth A → `None/404`.
- [ ] `get_active_membership` resuelve determinista (más reciente si hay histórico duplicado).
- [ ] `match_document_chunks` nunca recupera chunk de institución distinta.
- [ ] Auditoría de respuestas IA incluye `institucion_id` y `embedding_model` cuando corresponde.

## Referencias
- `migrations/001_multi_institution.sql`
- `migrations/004_unica_membresia_activa.sql`
- `tests/test_cross_tenant_routes.py`
- `tests/test_cross_tenant_repos.py`
