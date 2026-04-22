from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDefinition:
    name: str
    utterances: tuple[str, ...]
    keywords: tuple[str, ...]
    threshold: float = 0.34


budget_route = RouteDefinition(
    name="budget",
    utterances=(
        "quiero un presupuesto para implantar odoo",
        "necesitamos una propuesta economica para un erp",
        "cuanto cuesta implementar crm y facturacion",
        "buscamos precio para automatizar procesos en odoo",
        "queremos valorar modulos y coste de implantacion",
    ),
    keywords=(
        "presupuesto",
        "precio",
        "coste",
        "costo",
        "cotizacion",
        "cotización",
        "propuesta",
        "implantar",
        "implantacion",
        "implantación",
        "erp",
        "crm",
        "modulos",
        "módulos",
    ),
)

issue_route = RouteDefinition(
    name="issue",
    utterances=(
        "tenemos un error en odoo y necesitamos soporte",
        "no funciona el crm y aparece una incidencia",
        "hay un problema bloqueando el trabajo del equipo",
        "necesitamos ayuda con una falla en facturacion",
        "se ha roto una automatizacion y urge revisarlo",
    ),
    keywords=(
        "error",
        "problema",
        "incidencia",
        "soporte",
        "ayuda",
        "falla",
        "fallo",
        "bug",
        "bloqueado",
        "bloquea",
        "no funciona",
        "roto",
        "urgente",
    ),
)

discard_route = RouteDefinition(
    name="discard",
    utterances=(
        "hola solo queria saludar",
        "gracias por la informacion",
        "esto es una prueba sin peticion concreta",
        "test de mensaje interno",
        "consulta poco clara sin accion",
    ),
    keywords=(
        "hola",
        "gracias",
        "test",
        "prueba",
        "saludo",
        "interno",
    ),
    threshold=0.0,
)

routes = (budget_route, issue_route, discard_route)
