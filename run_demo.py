import asyncio
from pprint import pprint

from pipeline import run_demo_budget, run_demo_ticket


async def main():
    print("\nProbando intake_agent:")
    ticket_result = await run_demo_ticket()
    pprint(ticket_result)

    if ticket_result.get("error"):
        print("\n❌ Error en intake_agent:")
        print(ticket_result["error"])
        return

    print("\n✅ Intake agent ejecutado")
    print("Ticket ID:", ticket_result.get("ticket_id"))
    print("Partner ID:", ticket_result.get("partner_id"))
    print("Normalizado:", ticket_result.get("normalized_ticket"))

    print("\nProbando intake_agent + budget_agent:")
    budget_result = await run_demo_budget()
    pprint(budget_result)

    if budget_result.get("error"):
        print("\n❌ Error en el flujo completo:")
        print(budget_result["error"])

        print("\nDEBUG - Estado enviado al budget_agent:")
        pprint(budget_result["budget"]["debug"]["initial_state_sent_to_budget_agent"])

        print("\nDEBUG - Productos extraídos por el LLM:")
        pprint(budget_result["budget"]["debug"]["budget_lines_after_graph"])

        print("\nDEBUG - IDs devueltos por el LLM:")
        pprint(budget_result["budget"]["debug"]["product_ids_returned_by_llm"])

        print("\nDEBUG - Productos reales en Odoo:")
        pprint(budget_result["budget"]["debug"]["catalog_names"])

        print("\nDEBUG - IDs válidos de Odoo:")
        pprint(budget_result["budget"]["debug"]["valid_product_ids_from_odoo"])

        return

    print("\n✅ Flujo completo ejecutado")
    print("Ticket ID:", budget_result["ticket"].get("ticket_id"))
    print("Sale Order ID:", budget_result["budget"].get("sale_order_id"))
    print("Presupuesto:", budget_result["budget"].get("quote_summary"))


if __name__ == "__main__":
    asyncio.run(main())