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

sales_route = RouteDefinition(
    name="sales",
    utterances=(
        "queremos mejorar el proceso comercial",
        "necesitamos organizar oportunidades de venta",
        "buscamos una solucion para seguimiento comercial",
        "queremos automatizar el seguimiento de leads",
        "necesitamos mejorar el pipeline de ventas",
        "queremos centralizar la gestion comercial del equipo",
        "buscamos mejorar la captacion y conversion de clientes",
        "queremos ayuda para ordenar el area de ventas",
    ),
    keywords=(
        "ventas",
        "comercial",
        "pipeline",
        "lead",
        "leads",
        "oportunidades",
        "seguimiento comercial",
        "captacion",
        "captación",
        "conversion",
        "conversión",
        "equipo comercial",
        "crm comercial",
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

routes = (budget_route, sales_route, discard_route)
