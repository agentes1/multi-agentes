from dataclasses import dataclass

@dataclass(frozen=True)
class RouteDefinition:
    """Define una ruta del router semántico."""
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
        "necesitamos implantacion de odoo con crm y formacion",
        "queremos presupuesto para soporte mensual y desarrollo a medida",
        "queremos una oferta para personalizacion e integracion en odoo",
    ),
    keywords=(
        "presupuesto", "precio", "coste", "costo", "cotizacion", "cotización",
        "propuesta", "oferta", "implantar", "implantacion", "implantación",
        "erp", "odoo", "modulos", "módulos", "formacion", "formación",
        "soporte mensual", "desarrollo", "personalizacion", "personalización",
        "integracion", "integración", "automatizacion", "automatización",
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
        "quiero crear una oportunidad comercial",
    ),
    keywords=(
        "ventas", "venta", "comercial", "pipeline", "lead", "leads",
        "oportunidad", "oportunidades", "seguimiento comercial",
        "captacion", "captación", "conversion", "conversión",
        "equipo comercial", "crm comercial", "cliente interesado",
        "prospecto", "crear oportunidad", "nuevo lead",
    ),
)

rag_route = RouteDefinition(
    name="rag",
    utterances=(
        "tengo un problema con odoo",
        "me da un error al generar la factura",
        "no puedo acceder al modulo de ventas",
        "los correos entrantes no se procesan",
        "el sistema no funciona correctamente",
        "tengo una incidencia con el helpdesk",
        "me aparece un error en pantalla",
        "algo no funciona en odoo",
    ),
    keywords=(
        "error", "problema", "incidencia", "fallo", "no funciona",
        "no puedo", "no se procesa", "no aparece", "no accedo",
        "no genera", "no crea", "bug", "issue", "soporte",
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
        "esto es una prueba sin peticion concreta",
        "consulta poco clara sin accion",
    ),
    keywords=(
        "hola", "buenos dias", "buenas", "tiempo", "clima", "gracias",
        "test", "prueba", "saludo", "interno", "asistente",
        "informacion", "información",
    ),
    threshold=0.0,
)

routes = (budget_route, sales_route, rag_route, discard_route)