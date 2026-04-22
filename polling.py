from __future__ import annotations

from dataclasses import dataclass, field

from webhooks import TicketWebhookOrchestrator, build_odoo_service, build_ticket_webhook_orchestrator


@dataclass
class TicketPollingService:
    odoo_service_builder: callable = build_odoo_service
    orchestrator_builder: callable = build_ticket_webhook_orchestrator
    known_ticket_ids: set[int] = field(default_factory=set)

    async def poll_new_tickets(
        self,
        limit: int = 50,
        thread_prefix: str = "ticket-poll",
        model: str | None = None,
    ) -> dict:
        odoo_service = self.odoo_service_builder(model=model)
        tickets = odoo_service.get_helpdesk_tickets(limit=limit)

        discovered_ids = {
            int(ticket["id"])
            for ticket in tickets
            if ticket.get("id") is not None
        }
        new_ticket_ids = sorted(discovered_ids - self.known_ticket_ids)
        self.known_ticket_ids |= discovered_ids

        orchestrator: TicketWebhookOrchestrator = self.orchestrator_builder()
        results = []
        for ticket_id in new_ticket_ids:
            result = await orchestrator.handle_ticket_created(
                ticket_id=ticket_id,
                thread_id=f"{thread_prefix}-{ticket_id}",
                model=model,
            )
            results.append(result)

        return {
            "seen_ticket_ids": sorted(discovered_ids),
            "new_ticket_ids": new_ticket_ids,
            "processed_count": len(results),
            "results": results,
        }
