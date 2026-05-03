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
        "necesitamos implantacion de odoo con crm y formacion para el equipo",
        "queremos presupuesto para soporte mensual y desarrollo a medida",
        "buscamos una propuesta para ventas crm y automatizacion comercial",
        "necesitamos implantar odoo y capacitar al equipo",
        "queremos una oferta para personalizacion e integracion en odoo",
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
        "formacion",
        "formación",
        "soporte mensual",
        "desarrollo",
        "personalizacion",
        "personalización",
        "integracion",
        "integración",
        "automatizacion",
        "automatización",
        "ventas",
        "implantacion odoo",
    ),
)


issue_route = RouteDefinition(
    name="issue",
    utterances=(
        "tengo un error al usar odoo",
        "no funciona el crm",
        "hay una incidencia con facturacion",
        "la pantalla se queda bloqueada",
        "necesito ayuda con un problema tecnico",
        "me aparece un fallo al crear un pedido",
        "el sistema da error al guardar",
        "no puedo acceder al modulo",
        "tenemos un bug en ventas",
        "la integracion ha dejado de funcionar",
    ),
    keywords=(
        "error",
        "problema",
        "incidencia",
        "falla",
        "fallo",
        "bug",
        "no funciona",
        "bloqueado",
        "bloquea",
        "no puedo",
        "ayuda",
        "soporte",
        "acceder",
        "guardar",
        "integracion",
        "integraciÃ³n",
    ),
)


discard_route = RouteDefinition(
    name="discard",
    utterances=(
        "hola que tiempo hace",
        "buenos dias necesito informacion general",
        "hola asistente virtual",
        "gracias por la ayuda",
        "puedes responder a una duda general",
        "hola solo queria saludar",
        "gracias por la informacion",
        "esto es una prueba sin peticion concreta",
        "test de mensaje interno",
        "consulta poco clara sin accion",
    ),
    keywords=(
        "hola",
        "buenos dias",
        "buenas",
        "tiempo",
        "clima",
        "gracias",
        "test",
        "prueba",
        "saludo",
        "interno",
        "asistente",
        "informacion",
        "información",
    ),
    threshold=0.0,
)

routes = (budget_route, issue_route, discard_route)
