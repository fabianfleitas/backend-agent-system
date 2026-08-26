# Plan Multi-Institución — Decisiones Confirmadas

Fecha: 2026-08-24
Origen: adaptación FASE A-H del asistente institucional.
Estado: decisiones firmes registradas; no es código de ejecución.

---

## 1. Decisión sobre app_users.role (deprecación)

- **NO eliminar físicamente** la columna `app_users.role` de `tables.sql` ni de DB.
- **Dejar de consultar** `app_users.role` para decidir permisos institucionales.
- **Fuente autoritativa de permisos institucionales**: `institucion_miembros.tipo_miembro` (vía join/query en repositorios / `get_auth_context`).
- `app_users.role` puede mantenerse como campo de compatibilidad/legacy, pero ningún `require_*`, ningún repo, ningún servicio debe tomar decisiones de autorización basándose en él.
- Si se requiere sincronización, hacerlo por trigger o por proceso de onboarding, nunca como fuente de verdad de acceso.

---

## 2. Respuesta a accesos cruzados de institución (404)

- Si un administrador (o usuario) intenta acceder a un recurso de otra institución: **404** (no 403).
- Esto evita confirmar la existencia del recurso a un actor no autorizado.
- Aplicar en todos los servicios antes de operar por id: `documents_service`, `audio_service`, `conversations_service`, `chat_service`, `retrieval_service`, `audit_service`.
- `require_institution_admin()` y `require_member()` deben verificar primero que el recurso pertenezca a `auth.institucion_id`; si no, lanzar 404.
- El único bypass es `auth.is_platform_admin == true` (superadmin); en ese caso se permite acceso transversal a `/platform/*` y, si corresponde, a datos de cualquier institución con aviso explícito en observaciones/audit.

---

## 3. Separación clara: Administrador de institución vs Administrador de plataforma

| Concepto | Tabla / Fuente | Alcance | Endpoints (ejemplos) | Requiere institución |
|---|---|---|---|---|
| **Administrador institucional** | `institucion_miembros.tipo_miembro` (`ADMIN` / `SECRETARIA`) + `activo=true` + `fecha_salida IS NULL` | Solo su institución (`auth.institucion_id`) | `/api/admin/documents`, `/api/admin/audit`, `/api/admin/conversations`, `/api/admin/feedback`, `/api/admin/subscription` | **Sí**, obligatoria (1 usuario = 1 institución activa). Si no tiene membresía activa → 403 en negocio; `/me` puede funcionar sin institución. |
| **Administrador de plataforma (SUPERADMIN)** | `platform_admins` (`external_auth_id`, `is_active`) | Global / transversal a todas las instituciones | `/api/platform/instituciones`, `/api/platform/planes`, `/api/platform/suscripciones`, `/api/platform/usuarios`, `/api/platform/configuración` | **No**; puede operar sin pertenecer a ninguna institución. Se verifica solo con `is_platform_admin`. No debe mezclarse con `institucion_miembros`. |

### Regla operativa
- `platform_admins` es **ortogonal** a `institucion_miembros`.
- Un usuario puede ser `platform_admin` **y** miembro de una institución (por ejemplo, superadmin que también consulta su propia institución vía `/api/admin/*`). En ese caso, los endpoints `/api/admin/*` pueden requerir `require_member()` (institución) mientras `/api/platform/*` solo requiere `require_platform_admin()`.
- No se debe usar `institucion_miembros.tipo_miembro = 'ADMIN'` para dar acceso a `/api/platform/*`; eso sería confundir los dos conceptos.

---

## 4. Modelo de membresía (simplificado por decisión del usuario)

- Un usuario no debe pertenecer a varias instituciones en el modelo objetivo.
- Se mantiene `institucion_miembros` con `UNIQUE INDEX ... WHERE activo=true AND fecha_salida IS NULL` sobre `external_auth_id` para garantizar singularidad de membresía activa.
- Si un usuario cambia de institución, se realiza `deactivate` de la anterior y `add` a la nueva; no hay multi-pertenencia activa simultánea.
- Esto simplifica `get_auth_context`: no hay que resolver "institución activa" por header; se deriva directamente de la única membresía activa.

---

## 5. Actualizaciones de documentación derivadas

Las siguientes doc deben actualizarse para reflejar estas decisiones:

- `AGENTS.md`: reemplazar sección de auth delegada por auth Supabase; deprecación de `app_users.role`; definición de `platform_admins` vs `institucion_miembros`; regla 404 en acceso cruzado.
- `FRONTEND_API_INTEGRATION.md`: header `Authorization: Bearer <jwt>`; eliminación de `X-External-Auth-Id`, `X-User-Type`; nuevos endpoints `/api/platform/*`; regla de membresía única.
- `plan_sprints.md`: ordenar FASE A-H según el orden de ejecución confirmado (B primero para habilitar A, luego D, etc.).
- `README.md`: flujo JWT básico.
- `bruno/environments/*.bru`: actualizar fixtures de auth.

---

## 6. Notas del plan general (FASE A-H)

El plan completo de 8 fases (A: aislamiento; B: auth Supabase + RBAC; C: documental; D: RAG; E: conversaciones/voz; F: auditoría/PII; G: billing esquemas; H: dashboard) está documentado en el archivo de trabajo principal (`plan_multi_institucion.md` o equivalente creado en esta sesión). Las decisiones registradas aquí son la base para ese plan.

- **Auth**: Supabase Auth JWT (`sub` → `external_auth_id`). `get_auth_context()` resuelve usuario, `is_active`, membresía, `institucion_id`, `tipo_miembro`, `is_platform_admin`.
- **Aislamiento**: solo repositorios vía joins; `institucion_id` en tablas raíz; `match_document_chunks` con `p_institucion_id` + `es_version_activa=true`.
- **Defensa cruzada**: 404 en acceso a recurso ajeno; `require_institution_admin()` y `require_platform_admin()` separadas.
- **Deprecación**: `app_users.role` no se usa para autorización; se mantiene físicamente temporalmente.
- **Superadmin**: `platform_admins`; accesos globales en `/api/platform/*`; sin requerir institución.
