import pytest

from polling import TicketPollingService


class FakeOdooPollingService:
    def __init__(self, tickets: list[dict]):
        self._tickets = tickets

    def get_helpdesk_tickets(self, limit: int = 50):
        return self._tickets[:limit]


class FakeOrchestrator:
    def __init__(self):
        self.calls = []

    async def handle_ticket_created(self, ticket_id: int, thread_id: str | None = None, model=None):
        self.calls.append({"ticket_id": ticket_id, "thread_id": thread_id})
        return {
            "ok": True,
            "ticket": {"id": ticket_id},
            "trace": [f"processed:{ticket_id}"],
        }


def _build_odoo_service(tickets: list[dict]):
    def _builder(model: str | None = None):
        return FakeOdooPollingService(tickets)

    return _builder


def _build_orchestrator(orchestrator: FakeOrchestrator):
    def _builder():
        return orchestrator

    return _builder


@pytest.mark.asyncio
async def test_poll_new_tickets_processes_only_unseen_ids() -> None:
    orchestrator = FakeOrchestrator()
    service = TicketPollingService(
        odoo_service_builder=_build_odoo_service(
            [{"id": 10}, {"id": 11}, {"id": 12}]
        ),
        orchestrator_builder=_build_orchestrator(orchestrator),
        known_ticket_ids={10},
    )

    result = await service.poll_new_tickets(thread_prefix="poll-test")

    assert result["seen_ticket_ids"] == [10, 11, 12]
    assert result["new_ticket_ids"] == [11, 12]
    assert result["processed_count"] == 2
    assert [call["ticket_id"] for call in orchestrator.calls] == [11, 12]
    assert [call["thread_id"] for call in orchestrator.calls] == [
        "poll-test-11",
        "poll-test-12",
    ]


@pytest.mark.asyncio
async def test_poll_new_tickets_skips_when_everything_is_known() -> None:
    orchestrator = FakeOrchestrator()
    service = TicketPollingService(
        odoo_service_builder=_build_odoo_service([{"id": 20}, {"id": 21}]),
        orchestrator_builder=_build_orchestrator(orchestrator),
        known_ticket_ids={20, 21},
    )

    result = await service.poll_new_tickets()

    assert result["new_ticket_ids"] == []
    assert result["processed_count"] == 0
    assert result["results"] == []
    assert orchestrator.calls == []
