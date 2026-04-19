# Levantar Odoo con WSL (Ubuntu) — Guía paso a paso

## Contexto

El proyecto usa Odoo 18 + PostgreSQL 15 via Docker Compose.
**Docker Desktop está instalado en Windows** — es el método recomendado.
También existe Docker nativo en Ubuntu WSL 2, pero tiene problemas de red con Windows.

## Método recomendado: Docker Desktop

### Arrancar Docker Desktop desde terminal (sin abrir la app)

```powershell
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
```

Esperar ~30 segundos hasta que el daemon esté listo:

```powershell
docker ps  # debe responder sin error
```

Con Docker Desktop activo, `localhost:8069` funciona directamente desde Windows.

---

## 1. Verificar que Ubuntu WSL está disponible

```powershell
wsl -l -v
```

Debe aparecer `Ubuntu` en la lista. Si está `Stopped`, se inicia automáticamente con el siguiente paso.

---

## 2. Levantar los contenedores de Odoo

Con `systemd=true` en `/etc/wsl.conf`, Docker arranca solo al iniciar WSL.

```powershell
wsl -d Ubuntu -- bash -c "cd /mnt/c/Users/keess/Desktop/Proy_4/multi-agentes/odoo && docker compose up -d"
```

Esto arranca dos contenedores:
- `odoo-web-1` — Odoo 18.0 expuesto en el puerto `8069` de la IP de WSL
- `odoo-db-1` — PostgreSQL 15

---

## 3. Verificar que los contenedores están corriendo

```powershell
wsl -d Ubuntu -- bash -c "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
```

Ambos deben tener `STATUS = Up`. Espera ~30-40 segundos tras el `up -d`.

---

## 4. Obtener la IP de WSL para acceder desde Windows

```powershell
wsl -d Ubuntu -- bash -c "hostname -I | awk '{print \$1}'"
```

Esa IP (ej. `172.22.200.247`) es la dirección desde la que se accede a Odoo en el navegador Windows.

**Nota:** `localhost:8069` NO funciona desde Windows — hay que usar la IP de WSL directamente.

---

## 5. Crear la base de datos (solo la primera vez)

Abre en el navegador:
```
http://<IP_WSL>:8069/web/database/manager
```

Crea la BD con:
- **Database Name**: `odoo`
- **Email / Login**: `odoo`
- **Password**: `multi-agente-agentes1`

Espera ~1 minuto hasta que cargue el panel de Odoo.

---

## 6. Poblar la base de datos con productos y clientes

Desde dentro de WSL (donde `localhost:8069` sí funciona):

```powershell
wsl -d Ubuntu -- bash -c "cd /mnt/c/Users/keess/Desktop/Proy_4/multi-agentes && PYTHONPATH=/mnt/c/Users/keess/Desktop/Proy_4/multi-agentes python3 scripts/odoo_setup.py"
```

Esto instala módulos y crea:
- **Productos**: crm_base, email_ai, quotation_ai, odoo_connector, dashboard
- **Clientes**: ACME, MEGACORP

---

## 7. Ejecutar los tests de integración

```powershell
wsl -d Ubuntu -- bash -c "cd /mnt/c/Users/keess/Desktop/Proy_4/multi-agentes && PYTHONPATH=/mnt/c/Users/keess/Desktop/Proy_4/multi-agentes python3 -m pytest tests/test_odoo_api_wrapper.py -v"
```

Los tests usan solo `xmlrpc.client` (librería estándar) — no necesitan el venv de Windows.

---

## Parar los contenedores

```powershell
wsl -d Ubuntu -- bash -c "cd /mnt/c/Users/keess/Desktop/Proy_4/multi-agentes/odoo && docker compose down"
```

---

## Credenciales (shared/config.py)

| Campo    | Valor                              |
|----------|------------------------------------|
| URL      | `http://localhost:8069/xmlrpc/2`   |
| DB       | `odoo`                             |
| Usuario  | `odoo`                             |
| Password | `multi-agente-agentes1`            |

> **Nota:** Al ejecutar scripts desde Windows Python, la URL `localhost:8069` falla.
> Usar siempre WSL para ejecutar scripts que conecten a Odoo.

---

## Configuración WSL (`C:\Users\keess\.wslconfig`)

```ini
[wsl2]
# networkingMode=mirrored DESACTIVADO — rompe Docker (conflicto iptables)
```

Configuración de Ubuntu (`/etc/wsl.conf`):
```ini
[boot]
systemd=true

[user]
default=keess
```

Con `systemd=true`, el servicio Docker arranca automáticamente al iniciar WSL.

---

## Troubleshooting

| Problema | Solución |
|---|---|
| Contenedores se paran solos | Verificar que `networkingMode=mirrored` está desactivado en `.wslconfig` |
| `localhost:8069` no funciona desde Windows | Normal — usar IP de WSL o ejecutar desde dentro de WSL |
| Docker no arranca | `wsl -d Ubuntu -- bash -c "service docker start"` |
| BD `odoo` no existe | Crear desde `http://<IP_WSL>:8069/web/database/manager` |
| Credenciales incorrectas | Usuario es `odoo`, password `multi-agente-agentes1` |
| `No module named pytest` en WSL | `python3 -m pip install --user --break-system-packages pytest` |
