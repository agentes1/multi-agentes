import asyncio
from pprint import pprint

from pipeline import run_demo_ticket


async def main():
    result = await run_demo_ticket()
    pprint(result)

    if result.get("error"):
        print("\n❌ Error en el flujo:")
        print(result["error"])
        return

    print("\n✅ Flujo ejecutado")
    print("Ticket ID:", result.get("ticket_id"))
    print("Partner ID:", result.get("partner_id"))
    print("Normalizado:", result.get("normalized_ticket"))


if __name__ == "__main__":
    asyncio.run(main())