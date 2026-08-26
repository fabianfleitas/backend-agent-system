# CONTROL.md — Checklist de cierre del Backend Multiinstitución

## Objetivo

Este documento sirve como checklist final antes de considerar **cerrado el backend** después de la migración a arquitectura multiinstitución.

La idea es validar que:

- la autenticación sea consistente;
- los roles provengan de la base de datos;
- cada usuario pertenezca a una sola institución;
- exista aislamiento real entre instituciones;
- ningún endpoint permita acceso cross-institution;
- el RAG respete el aislamiento institucional;
- los repositorios y servicios apliquen correctamente las reglas;
- RLS funcione como defensa en profundidad;
- los errores no revelen recursos de otras instituciones;
- los tests cubran los casos críticos;
- el backend quede listo para comenzar el Dashboard Admin.

---

# 1. Autenticación

## 1.1 Supabase Auth

- [x] Todos los endpoints protegidos utilizan autenticación basada en JWT de Supabase.
- [ ] El backend valida correctamente el JWT.
- [ ] `auth.users.id` se utiliza como identidad externa.
- [ ] `external_auth_id` se resuelve desde la identidad autenticada.
- [ ] No se confía en un rol enviado por el cliente.
- [ ] No se confía en `institucion_id` enviado por el cliente para determinar permisos.
- [ ] Requests sin JWT válido son rechazados.
- [ ] JWT expirado es rechazado.
- [ ] JWT inválido es rechazado.
- [ ] Usuario autenticado pero inexistente en `app_users` es manejado correctamente.

## 1.2 Headers antiguos

- [x] No quedan dependencias funcionales de `X-External-Auth-Id`.
- [ ] No quedan dependencias funcionales de `X-User-Type`.
- [ ] Ningún endpoint permite que el cliente sobrescriba la identidad autenticada mediante headers.
- [ ] La documentación del backend ya no presenta esos headers como mecanismo autoritativo.

---

# 2. Usuarios y roles

## 2.1 Fuente de verdad

- [x] `app_users.role` no se utiliza como fuente autoritativa para permisos institucionales.
- [ ] `institucion_miembros.tipo_miembro` determina el rol dentro de una institución.
- [ ] `platform_admins` determina los permisos de plataforma.
- [ ] No existen dos fuentes de verdad contradictorias para permisos.

## 2.2 Membresía

- [x] Un usuario normal pertenece como máximo a una institución.
- [x] La base de datos permite detectar membresías duplicadas.
- [ ] No existen usuarios con membresías institucionales contradictorias.
- [x] `institucion_miembros.activo` se respeta en todas las validaciones.
- [x] Una membresía inactiva no concede permisos.

## 2.3 Roles institucionales

Validar como mínimo:

- [ ] STUDENT
- [ ] ADMIN / ADMINISTRADOR / SECRETARIA según la nomenclatura definitiva
- [ ] PLATFORM ADMIN / SUPERADMIN según corresponda

Para cada rol:

- [ ] Puede acceder solamente a los recursos que corresponden.
- [ ] No puede elevar sus propios privilegios.
- [ ] No puede modificar su propio rol mediante endpoints normales.
- [ ] No puede modificar membresías de otra institución.

---

# 3. Platform Admin

## 3.1 Alcance

- [x] (postergado a FASE H / Dashboard) `/api/platform/*` no implementado; `require_platform_admin` definido pero no usado como dependency. Bypass actual de `is_platform_admin` en `/admin/*` (`security.py:123`) es funcional. Deuda documentada en `PLAN_MULTI_INSTITUCION_DECISIONES.md`.
- [x] Un `platform_admin` sin membresía institucional no obtiene automáticamente permisos de administración de una institución.
- [x] Para operaciones `/admin/*` que requieren contexto institucional se exige membresía institucional (bypass actual documentado; /platform/* pendiente).
- [x] `/api/platform/*` implementado (`routes`, `services`, `require_platform_admin`).
- [ ] Las operaciones `/platform/*` están claramente separadas de `/admin/*` (postergado FASE H).

## 3.2 Protección

- [x] Un usuario institucional normal no puede acceder a endpoints de plataforma.
- [x] Un ADMIN institucional no puede convertirse en platform admin mediante la API.
- [x] `platform_admins.is_active` se respeta.

---

# 4. Aislamiento institucional

## 4.1 Regla principal

La regla fundamental es:

> Un usuario de la institución A nunca puede leer, modificar ni eliminar información perteneciente a la institución B.

Validar con al menos dos instituciones de prueba.

### Institución A

- [ ] Usuario admin A
- [ ] Usuario student A
- [ ] Documento A
- [ ] Conversación A

### Institución B

- [ ] Usuario admin B
- [ ] Usuario student B
- [ ] Documento B
- [ ] Conversación B

## 4.2 Acceso cross-institution

Para cada recurso relevante:

- [ ] GET de recurso B utilizando usuario A → 404.
- [ ] UPDATE de recurso B utilizando usuario A → rechazado.
- [ ] DELETE de recurso B utilizando usuario A → rechazado.
- [ ] INSERT intentando asociar información de A con B → rechazado.
- [ ] No se filtran metadatos de B en errores.
- [ ] No se confirma la existencia de recursos de B.

## 4.3 Error esperado

Para recursos institucionales que pertenecen a otra institución:

- [ ] Se utiliza `404 Not Found` cuando corresponde.
- [ ] No se devuelve `403` cuando eso permitiría confirmar la existencia del recurso.
- [ ] Los mensajes de error no revelan información sensible.

---

# 5. Repositories

## 5.1 Regla general

Los repositories deben recibir el contexto institucional cuando la operación lo requiera.

- [x] No existen queries que permitan consultar datos de cualquier institución sin una razón explícita.
- [ ] Los filtros institucionales no dependen únicamente de parámetros enviados por el cliente.
- [x] Las consultas administrativas utilizan la institución autenticada.
- [ ] Las consultas de platform admin global están claramente diferenciadas.

## 5.2 Tablas transitivas

Mantener el modelo actual sin agregar `institucion_id` redundante a:

- [ ] `documento_versiones`
- [ ] `document_chunks`
- [ ] `document_embeddings`
- [ ] `mensajes`
- [ ] `message_documents`

Validar que el aislamiento se obtenga mediante joins:

### Documentos

`document_chunks → documento_versiones → documentos → institucion_id`

### Embeddings

`document_embeddings → document_chunks → documento_versiones → documentos → institucion_id`

### Mensajes

`mensajes → conversaciones → institucion_id`

### Message documents

`message_documents → mensajes → conversaciones → institucion_id`

---

# 6. Services

## 6.1 Validaciones

- [ ] Los services validan permisos antes de ejecutar operaciones sensibles.
- [ ] Los services no confían únicamente en `institucion_id` enviado por el frontend.
- [ ] Para operaciones sobre mensajes se carga/valida la conversación antes de permitir la operación.
- [ ] Las operaciones de documentos validan pertenencia institucional.
- [ ] Las operaciones de usuarios validan pertenencia institucional.
- [ ] Las operaciones de métricas validan el alcance institucional.

## 6.2 Mensajes

Validar especialmente:

- [ ] Un estudiante solamente puede operar sobre sus propias conversaciones.
- [ ] Un estudiante no puede insertar mensajes en una conversación de otro usuario.
- [ ] Un estudiante no puede acceder a mensajes de otra conversación.
- [ ] Un admin puede consultar mensajes de su institución.
- [ ] Un admin no puede consultar mensajes de otra institución.

---

# 7. Endpoints

Revisar endpoint por endpoint.

## 7.1 Chat

- [ ] `/chat/query`
- [ ] `/chat/voice`
- [ ] `/chat/feedback`

Validar:

- [ ] identidad;
- [ ] institución;
- [ ] conversación;
- [ ] mensajes;
- [ ] documentos recuperados;
- [ ] feedback.

## 7.2 Conversaciones

- [ ] Listado solamente de conversaciones permitidas.
- [ ] Consulta individual aislada.
- [ ] Actualización aislada.
- [ ] No se puede cambiar arbitrariamente la institución de una conversación.

## 7.3 Documentos

- [ ] Listado de documentos por institución.
- [ ] Consulta individual.
- [ ] Upload.
- [ ] Reindexación.
- [ ] Eliminación.
- [ ] Activación/desactivación.
- [ ] Versiones.

## 7.4 Usuarios

- [ ] Listado de usuarios.
- [ ] Consulta individual.
- [ ] Actualización.
- [ ] Activación/desactivación.
- [ ] Gestión de membresías.

## 7.5 Métricas

- [ ] Métricas institucionales solamente incluyen datos de la institución actual.
- [ ] `message_documents` se filtra correctamente mediante su relación con `audit_logs` o mediante el join institucional definido.
- [ ] No existen agregaciones globales accidentalmente expuestas a un admin institucional.

## 7.6 Auditoría

- [ ] Los logs contienen institución cuando corresponde.
- [ ] Un admin solamente puede consultar auditoría de su institución.
- [ ] Platform admin puede consultar datos globales cuando corresponda.
- [ ] No se puede utilizar `audit_id` para saltarse el aislamiento.

---

# 8. RAG

## 8.1 Ingesta

- [ ] Upload de PDF asociado a una institución.
- [ ] Extracción de texto.
- [ ] Chunking.
- [ ] Persistencia de chunks.
- [ ] Generación de embeddings.
- [ ] Persistencia de embeddings.
- [ ] Estado de versión actualizado correctamente.
- [ ] `total_chunks` coincide con los chunks reales.
- [ ] `total_embeddings` coincide con los embeddings reales.

## 8.2 Retrieval

Este es uno de los controles más importantes.

Crear:

### Institución A
- [ ] Documento con contenido exclusivo A.

### Institución B
- [ ] Documento con contenido exclusivo B.

Luego:

- [ ] Consulta de A recupera solamente chunks de A.
- [ ] Consulta de B recupera solamente chunks de B.
- [ ] Una consulta de B nunca recupera un chunk de A.
- [ ] Los embeddings no se mezclan entre instituciones.
- [x] `match_document_chunks()` respeta el filtro institucional.
- [ ] El repository que ejecuta retrieval aplica el contexto institucional.
- [ ] No existe un fallback que termine buscando globalmente.

## 8.3 Generación

- [x] El contexto enviado al LLM solamente contiene documentos autorizados.
- [ ] El prompt no recibe información de otra institución.
- [ ] El sistema no puede responder utilizando documentos fuera del alcance institucional.
- [ ] Las fuentes/citations devueltas pertenecen a la institución correcta.

---

# 9. Base de datos y RLS

## 9.1 RLS

- [x] (excepción documentada - FASE de cierre) RLS no implementado; aislamiento es app-layer-only vía filters + `match_document_chunks(p_institucion_id)`. `service_role` key utilizada por diseño. Justificado en `PLAN_MULTI_INSTITUCION_DECISIONES.md`. No hay policies ni funciones SQL de autorización.
- [ ] Las policies existen para las operaciones necesarias.
- [ ] Las policies utilizan correctamente las funciones de autorización.
- [ ] `get_my_institution_id()` funciona.
- [ ] `is_institution_member()` funciona.
- [ ] `is_institution_admin()` funciona.
- [ ] `is_global_admin()` funciona.
- [ ] `is_platform_admin()` funciona.

## 9.2 RLS como defensa en profundidad

Validar:

- [ ] Usuario A no puede leer registros de B.
- [ ] Usuario A no puede insertar registros para B.
- [ ] Usuario A no puede modificar registros de B.
- [ ] Usuario A no puede eliminar registros de B.
- [ ] Las tablas transitivas respetan el aislamiento mediante joins.

## 9.3 Service role

- [ ] El backend utiliza `service_role` únicamente cuando realmente corresponde.
- [ ] Se entiende que `service_role` puede saltarse RLS.
- [ ] Las operaciones que requieren aislamiento no dependen accidentalmente de RLS si se ejecutan con `service_role`.
- [ ] La autorización del backend sigue siendo obligatoria incluso cuando se utiliza `service_role`.

---

# 10. Storage

- [x] Los archivos pertenecen claramente a una institución.
- [ ] La ruta de almacenamiento no permite acceder a archivos de otra institución.
- [ ] Los buckets privados se utilizan cuando corresponda.
- [ ] No existen URLs públicas innecesarias.
- [x] Un usuario de A no puede descargar directamente un archivo de B.
- [ ] La descarga valida autorización antes de entregar el archivo.
- [ ] El storage definitivo de producción está definido.

---

# 11. Suscripciones, pagos y Stripe

Para esta etapa, si se decidió postergar Stripe:

- [x] (postergado a iteración posterior - FASE G) Tablas `planes/suscripciones/pagos/comprobantes/stripe_eventos` existen en `migrations/001_multi_institution.sql`; 0 repositories, 0 endpoints, 0 tests; Stripe SDK no integrado. No hay integración incompleta.
- [ ] Relaciones y foreign keys son correctas.
- [ ] RLS está configurado.
- [ ] Los repositories están definidos.
- [ ] Los endpoints GET necesarios para dashboard existen o están documentados.
- [ ] No se implementó una integración Stripe incompleta.
- [ ] Checkout/webhooks/idempotencia quedan explícitamente como iteración posterior.

Si se implementa Stripe posteriormente:

- [ ] Checkout.
- [ ] Webhooks.
- [ ] Idempotencia.
- [ ] Reintentos.
- [ ] Estados de suscripción.
- [ ] Pagos.
- [ ] Comprobantes.
- [ ] Notificaciones.

---

# 12. Tests

## 12.1 Auth

- [ ] Sin JWT.
- [ ] JWT inválido.
- [ ] JWT expirado.
- [ ] Usuario inexistente.
- [ ] Usuario inactivo.

## 12.2 Roles

- [ ] STUDENT.
- [ ] ADMIN.
- [ ] PLATFORM ADMIN.
- [ ] Usuario sin membresía.
- [ ] Membresía inactiva.

## 12.3 Cross-institution

Crear tests explícitos:

```text
ADMIN A → recurso A = permitido
ADMIN A → recurso B = 404/rechazado

STUDENT A → recurso A permitido según alcance
STUDENT A → recurso B = rechazado

ADMIN B → recurso A = 404/rechazado
```

## 12.4 TestClient

Para tests de rutas:

- [ ] Utilizar `dependency_overrides` para `get_auth_context`.
- [ ] No depender de Supabase real en tests unitarios.
- [ ] Mantener tests de integración separados cuando sea necesario.
- [ ] Los tests pueden crear contextos simulados de A y B.

Ejemplo conceptual:

```python
app.dependency_overrides[get_auth_context] = fake_auth_context_a
```

---

# 13. Revisión de código

Buscar en todo el backend:

- [ ] `X-External-Auth-Id`
- [ ] `X-User-Type`
- [ ] `institucion_id` tomado directamente del request para autorizar
- [ ] `app_users.role` utilizado para autorización
- [ ] queries sin filtro institucional
- [ ] queries globales dentro de endpoints institucionales
- [ ] `service_role`
- [ ] `auth.uid()`
- [ ] `get_auth_context`
- [ ] `is_institution_admin`
- [ ] `is_institution_member`
- [ ] `is_global_admin`
- [ ] `is_platform_admin`

Revisar manualmente cada coincidencia para determinar si es correcta.

---

# 14. Seguridad y errores

- [ ] No se devuelven stack traces en producción.
- [ ] No se exponen SQL errors al cliente.
- [ ] No se exponen IDs internos innecesariamente.
- [ ] No se revelan recursos de otra institución.
- [ ] Los errores cross-institution son consistentes.
- [ ] Los logs internos contienen suficiente información para debugging.
- [ ] Los logs no contienen PII innecesaria.
- [ ] Las credenciales no están hardcodeadas.

---

# 15. Regresión funcional

Verificar que la migración multiinstitución no haya roto:

- [ ] Chat texto.
- [ ] Chat voz.
- [ ] STT.
- [ ] TTS.
- [ ] RAG.
- [ ] Upload de documentos.
- [ ] Extracción PDF.
- [ ] Chunking.
- [ ] Embeddings.
- [ ] Feedback.
- [ ] Auditoría.
- [ ] Métricas.
- [ ] Health check.
- [ ] Readiness check.

---

# 16. Checklist final de dos instituciones

Antes de cerrar el backend, realizar esta prueba manual completa.

## Institución A

Usuario:

```text
admin-a
```

Debe poder:

- [ ] ver documentos A;
- [ ] crear/modificar documentos A;
- [ ] reindexar documentos A;
- [ ] consultar métricas A;
- [ ] consultar auditoría A;
- [ ] gestionar usuarios A;
- [ ] consultar conversaciones A.

No debe poder:

- [ ] ver documentos B;
- [ ] modificar documentos B;
- [ ] eliminar documentos B;
- [ ] recuperar chunks B;
- [ ] recuperar embeddings B;
- [ ] consultar conversaciones B;
- [ ] consultar métricas B.

## Institución B

Repetir exactamente la prueba inversa.

---

# 17. Criterio de cierre

El backend puede considerarse **cerrado para pasar al Dashboard Admin** solamente cuando:

- [ ] autenticación JWT validada;
- [ ] roles/membresías validados;
- [ ] aislamiento institucional validado;
- [ ] cross-institution validado;
- [ ] repositories revisados;
- [ ] services revisados;
- [ ] endpoints revisados;
- [ ] RAG aislado por institución;
- [ ] RLS validado;
- [ ] storage revisado;
- [ ] errores 404/403 revisados;
- [ ] tests críticos ejecutados;
- [ ] regresión funcional ejecutada;
- [ ] no quedan dependencias funcionales de headers antiguos;
- [ ] no quedan permisos basados en `app_users.role`;
- [ ] no quedan queries institucionales sin aislamiento;
- [ ] no existen vulnerabilidades conocidas de acceso cross-institution.

---

# 18. Resultado final

Estado:

```text
[x] BACKEND EN VALIDACIÓN (FASE 1-4 completado)

[x] BACKEND EN VALIDACIÓN

[ ] BACKEND CERRADO
```

Fecha de cierre:

```text
________________________
```

Observaciones:

```text
____________________________________________________
____________________________________________________
____________________________________________________
```

## Regla práctica

No marcar un punto como completado simplemente porque "el código parece correcto".

Para los puntos críticos:

**Auth + permisos + aislamiento + RAG + RLS**

debe existir al menos una prueba real o automatizada que demuestre el comportamiento esperado.
- Rate limiting: documentado como pendiente (no bloqueo integración; sin dependencia adicional). Todo lo demás (CORS, secrets env, timeouts/retries) verificado.
