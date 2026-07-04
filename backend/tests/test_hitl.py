import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.negotiation import NegotiationPlanOut
from app.api.app import create_app
from app.api.deps import get_llm
from app.db.seed import seed
from app.db.session import get_session
from app.llm.stub import StubLLM


def _bad_plan_stub():
    # upfront 15% (<30 breach), extension 45d (>30 breach); installments sum to invoice
    bad = NegotiationPlanOut(upfront_pct=15, extension_days=45, installments=[
        {"seq": 1, "label": "Upfront", "amount_paise": 36000_00, "due_offset_days": 0},
        {"seq": 2, "label": "Balance", "amount_paise": 204000_00, "due_offset_days": 45},
    ])
    return StubLLM(text_response="Namaste Anand ji, about INV-2291.", structured_response=bad)


@pytest.mark.db
async def test_escalation_persisted_and_resolved(session):
    await seed(session)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_llm] = lambda: _bad_plan_stub()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = (await client.post("/buyers/anand/run-cycle")).json()
        assert res["decision"] == "escalate"
        eid = res["escalation_id"]
        assert eid

        out = (await client.post(f"/escalations/{eid}/resolve",
                                 json={"action": "approve"})).json()
        assert out["resolved"] is True
        assert out["resolution"] == "approved"

        # Spec: on approve -> dispatch + memory. The approved send must land
        # in the memory layer like any ACT-path send.
        from sqlalchemy import func, select
        from app.db.models import MemoryRecordRow
        n_mem = (await session.execute(
            select(func.count()).select_from(MemoryRecordRow)
            .where(MemoryRecordRow.buyer_id == "anand"))).scalar_one()
        assert n_mem >= 1


@pytest.mark.db
async def test_override_records_owner_choice(session):
    await seed(session)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_llm] = lambda: _bad_plan_stub()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = (await client.post("/buyers/anand/run-cycle")).json()
        eid = res["escalation_id"]
        out = (await client.post(f"/escalations/{eid}/resolve",
                                 json={"action": "override"})).json()
        assert out["resolved"] is True
        assert out["resolution"] == "overridden"
