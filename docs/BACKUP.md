# Backup de la base de datos (RNF-06)

Mecanismo de respaldo diario con retención de 7 días, documentado para operar
(véase S6). La tesis define: copias automáticas diarias de la base de datos
vectorial y documental con retención de 7 días.

## Herramienta

`backend-agent-system/scripts/backup_db.py` — usa `pg_dump` contra `DATABASE_URL`
(connection string de Postgres/Supabase) y vuelca a `BACKUP_DIR` (default
`backups/`) con purga de archivos más antiguos que `BACKUP_RETENTION_DAYS`
(default 7).

## Configuración

En `.env`:

```bash
DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
BACKUP_DIR=backups
BACKUP_RETENTION_DAYS=7
```

> La `DATABASE_URL` es la connection string de la consola de Supabase
> (Settings → Database → Connection string), **no** la service role key.
> No se incluye en el repositorio.

## Ejecución manual

```bash
cd backend-agent-system
python3 scripts/backup_db.py
```

Salida: `backups/<fecha>_<hora>.sql` y eliminación de copias vencidas.

## Programar cron diario

```cron
# respaldo diario a las 03:00
0 3 * * * cd /ruta/backend-agent-system && DATABASE_URL="postgresql://..." python3 scripts/backup_db.py >> backups/cron.log 2>&1
```

## Prueba de restauración (criterio de aceptación)

```bash
createdb restauracion_prueba
pg_restore --no-owner --dbname=restauracion_prueba backups/<fecha>_<hora>.sql
psql restauracion_prueba -c "SELECT count(*) FROM documentos;"
dropdb restauracion_prueba
```

El criterio RNF-06 se cumple si la información puede recuperarse conservando su
integridad.

## Alternativa

Supabase ofrece **backups gestionados / PITR** según el plan. Si se usa esa
opción, documentar la retención en el panel (≥ 7 días) en lugar del script; el
script queda disponible como complemento.