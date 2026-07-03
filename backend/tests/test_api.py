import pytest
from httpx import ASGITransport, AsyncClient

from app.api.app import create_app
from app.api.deps import get_llm
from app.db.seed import seed
from app.db.session import get_session
from app.llm.stub import StubLLM


@pytest.mark.db
async def test_run_cycle_escalates_for_anand(session):
    await seed(session)

    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_llm] = lambda: StubLLM(
        text_response="Namaste Anand ji, a reminder about INV-2291.")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        buyers = (await client.get("/buyers")).json()
        assert any(b["id"] == "anand" for b in buyers)

        cal = (await client.get("/cash-calendar")).json()
        assert cal["days"] and cal["week"]

        # Anand's thread ends with "pay over a few weeks" -> negotiation runs.
        # StubLLM cannot return a structured plan, so the cycle escalates (LLM error path).
        res = (await client.post("/buyers/anand/run-cycle")).json()
        assert res["decision"] == "escalate"
        assert res["escalation_reason"]
