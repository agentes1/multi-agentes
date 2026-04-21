# Levantar Todo El Proyecto (Solo Rutas Relativas)

Esta guía está pensada para ejecutarse desde la raíz del repositorio `multi-agentes`.
No usa rutas absolutas.

## 1) Ir a la raíz del repositorio

Si aún no estás en la carpeta del proyecto:

```powershell
cd multi-agentes
```

## 2) Crear y activar entorno virtual (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 3) Levantar Odoo + PostgreSQL con Docker

Desde la raíz del repo:

```powershell
docker compose -f odoo/docker-compose.yaml up -d
```

Verificar que está arriba:

```powershell
docker compose -f odoo/docker-compose.yaml ps
```

## 4) Inicializar base de datos Odoo (primera vez)

Abrir en navegador:

```text
http://localhost:8069/web/database/manager
```

Crear base con:
- Database Name: `odoo`
- Login: `odoo`
- Password: `multi-agente-agentes1`

## 5) Cargar datos semilla en Odoo

Los scripts importan módulos del proyecto, por eso se ejecutan con `PYTHONPATH=.`.

```powershell
$env:PYTHONPATH = "."
python scripts/odoo_setup.py
python scripts/setup_helpdesk.py
```

## 6) Levantar la API del proyecto

En otra terminal, también ubicada en la raíz del repo y con el venv activo:

```powershell
python api.py
```

Endpoints útiles:
- Health: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`

## 7) Ejecutar tests

### Tests rápidos (sin integración)

```powershell
python -m pytest tests -q -m "not integration"
```

### Tests de integración (requiere Odoo arriba)

```powershell
python -m pytest tests -q -m integration
```

### Todos los tests

```powershell
python -m pytest tests -q
```

## 8) Ejecutar evaluación multi-modelo (opcional)

```powershell
python -m evals.run_multi_model_eval --cases evals/benchmark_cases.jsonl --models qwen2.5 qwen3 llama3 --out-dir evals/reports
```

## 9) Parar servicios Docker

```powershell
docker compose -f odoo/docker-compose.yaml down
```

## 10) Flujo recomendado en 3 terminales

Terminal 1:

```powershell
cd multi-agentes
.\.venv\Scripts\Activate.ps1
docker compose -f odoo/docker-compose.yaml up -d
```

Terminal 2:

```powershell
cd multi-agentes
.\.venv\Scripts\Activate.ps1
python api.py
```

Terminal 3:

```powershell
cd multi-agentes
.\.venv\Scripts\Activate.ps1
python -m pytest tests -q
```
