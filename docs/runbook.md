# Runbook — operación de n8n (self-hosted)

## Dónde vive

- Contenedor: `n8n` (red `host`, escucha en `127.0.0.1:5678`)
- Datos: **bind mount** `/home/fperez/homelab/hermes-repos/ai-automation/n8n/data` → `/home/node/.n8n`
- Publicado por Caddy en `https://wa.fperez.top/webhook/...`

## Operaciones

### Importar o actualizar un workflow (vía normal)

```bash
docker cp workflows/<archivo>.json n8n:/tmp/wf.json
docker exec n8n n8n import:workflow --input=/tmp/wf.json
docker exec n8n n8n update:workflow --id=<id> --active=true
docker restart n8n        # obligatorio: el webhook se registra al arrancar
```

El JSON **debe traer `"id"`**; si falta, el import falla con
`SQLITE_CONSTRAINT: NOT NULL constraint failed: workflow_entity.id`.

### Verificar

```bash
docker exec n8n n8n list:workflow
curl -s -X POST http://127.0.0.1:5678/webhook/whatsapp-dental \
  -H 'Content-Type: application/json' -d '{"from":"56900000001","text":"hola"}'
```

## Trampa importante: editar la base SQLite

**Nunca copiar `database.sqlite` con el contenedor corriendo ni sin el WAL.**
n8n trabaja en modo WAL: los imports y cambios recientes viven en
`database.sqlite-wal`. Copiar solo `database.sqlite` devuelve un estado viejo y,
si después se reemplaza la base con esa copia, se pierden los workflows importados.

Si hace falta editar la base a mano:

1. `docker stop n8n` (cierra y hace checkpoint limpio).
2. Copiar **los tres** archivos: `database.sqlite`, `-wal`, `-shm`.
3. Editar la copia con sqlite3.
4. Devolver la copia editada **y borrar `-wal` / `-shm`** del directorio de datos.
5. `docker start n8n`.

Mejor alternativa: no borrar workflows por SQL. n8n no tiene `delete:workflow` en CLI;
usar la API REST con una API key, o simplemente **desactivar** el workflow.

## Estado actual

- Un solo workflow activo: `demoWhatsAppDental1` (asistente de la clínica).
- El resto de demos se eliminaron; backup en `/home/fperez/homelab/backups/pre-consolidacion-20261028/`.
