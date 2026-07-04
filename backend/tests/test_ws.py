import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.agents.negotiation import NegotiationPlanOut
from app.api.app import create_app
from app.api.deps import get_llm
from app.config import settings
from app.db import models  # noqa: F401  (register tables)
from app.db.base import Base
from app.db.seed import seed
from app.db.session import get_session, make_engine, make_session_factory
from app.llm.stub import StubLLM


def _bad_plan_stub():
    bad = NegotiationPlanOut(upfront_pct=15, extension_days=45, installments=[
        {"seq": 1, "label": "Upfront", "amount_paise": 36000_00, "due_offset_days": 0},
        {"seq": 2, "label": "Balance", "amount_paise": 204000_00, "due_offset_days": 45},
    ])
    return StubLLM(text_response="Namaste Anand ji, about INV-2291.",
                   structured_response=bad)


# TestClient drives the app on its own event loop, so the WS tests provision
# their own engine per dependency call instead of reusing the async fixtures
# (asyncpg connections are bound to the loop that created them).

async def _setup_db():
    eng = make_engine(settings.test_database_url)
    try:
        try:
            async with eng.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:  # noqa: BLE001
            pass
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        async with make_session_factory(eng)() as s:
            await seed(s)
    finally:
        await eng.dispose()


async def _session_dep():
    eng = make_engine(settings.test_database_url)
    try:
        async with make_session_factory(eng)() as s:
            yield s
    finally:
        await eng.dispose()


def _app():
    try:
        asyncio.run(_setup_db())
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres+pgvector not available: {exc}")
    app = create_app()
    app.dependency_overrides[get_session] = _session_dep
    app.dependency_overrides[get_llm] = _bad_plan_stub
    return app


@pytest.mark.db
def test_ws_pushes_new_escalation_and_resolves():
    client = TestClient(_app())
    with client.websocket_connect("/ws/escalations") as ws:
        res = client.post("/buyers/anand/run-cycle")
        assert res.status_code == 200
        eid = res.json()["escalation_id"]
        assert eid

        pushed = ws.receive_json()
        assert pushed["type"] == "escalation"
        assert pushed["escalation_id"] == eid
        assert pushed["buyer_id"] == "anand"
        assert pushed["amount"].startswith("₹")

        ws.send_json({"action": "approve", "escalation_id": eid})
        ack = ws.receive_json()
        assert ack["type"] == "resolution"
        assert ack["resolution"] == "approved"

        fanout = ws.receive_json()
        assert fanout["type"] == "escalation_resolved"
        assert fanout["escalation_id"] == eid


@pytest.mark.db
def test_ws_override_and_unknown_escalation():
    client = TestClient(_app())
    with client.websocket_connect("/ws/escalations") as ws:
        ws.send_json({"action": "approve", "escalation_id": "ghost"})
        err = ws.receive_json()
        assert err["type"] == "error"

        res = client.post("/buyers/anand/run-cycle")
        eid = res.json()["escalation_id"]
        ws.receive_json()  # pushed escalation event

        ws.send_json({"action": "override", "escalation_id": eid})
        ack = ws.receive_json()
        assert ack["resolution"] == "overridden"
