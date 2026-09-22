# RLS — Estado y decisión de diseño

Fecha de revisión: 2026-09-20

## Estado real

- Las policies de RLS **viven en la base real de Supabase**, no están materializadas en
  migraciones de este repo (verificado: no hay `CREATE POLICY`/`ROW LEVEL SECURITY` en
  `migrations/` ni `tables.sql`).
- El backend usa **`service_role`** (clave de servicio), que **bypassa RLS** por diseño
  (`force_rls = false`). El aislamiento principal se implementa en la capa de aplicación:
  los repositorios filtran por `institucion_id`/`external_auth_id` y los servicios devuelven
  `404` para recursos cross-tenant.
- Funciones helper presentes en la DB real (verificado en el cierre 2026-08-29):
  `is_global_admin`, `is_platform_admin`, `is_institution_admin`, `is_institution_member`,
  `get_my_institution_id`.

## Decisión de diseño

- **RLS es defensa en profundidad** para accesos que NO usen `service_role` (p. ej. acceso
  directo a la DB desde otras herramientas). No es la barrera principal del sistema.
- No se materializan policies en migraciones en este repo porque la fuente de verdad es la
  DB de Supabase y el backend no las requiere para su funcionamiento.

## Pendiente (mantenimiento)

- Si se audita la DB real, revisar:
  - policies excesivamente permisivas (que no filtren por tenant),
  - funciones `SECURITY DEFINER` (riesgo de escalada si no acotan `search_path`),
  - `search_path` en funciones SQL,
  - mantener RLS como defensa para accesos no-`service_role`.
- Documentar en este archivo cualquier cambio de policy aplicado en la DB.