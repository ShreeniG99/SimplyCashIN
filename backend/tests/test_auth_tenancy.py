import datetime as dt

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.app import create_app
from app.api.deps import get_owner_id
from app.config import settings
from app.db import models as m
from app.db.seed import seed
from app.db.session import get_session

SECRET = "test-jwt-secret"


def _token(owner_id: str, secret: str = SECRET) -> dict:
    tok = pyjwt.encode({"sub": owner_id, "aud": "authenticated"}, secret,
                       algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


async def _seed_second_owner(session):
    session.add(m.OwnerRow(id="meera", name="Meera Nair", business="Nair Textiles",
                           max_extension_days=20, min_upfront_pct=40))
    session.add(m.BuyerRow(id="chennai-silks", owner_id="meera", name="Chennai Silks",
                           tier="Regular · 2 yrs", relationship_years=2.0,
                           on_time_rate=0.7, preferred_channel="WhatsApp Business"))
    session.add(m.InvoiceRow(id="inv-cs", buyer_id="chennai-silks", number="INV-9001",
                             amount_paise=50000_00, due_date=dt.date(2026, 5, 10),
                             status="overdue", days_overdue=8))
    await session.commit()


def _client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_dev_fallback_resolves_to_ramesh():
    assert settings.supabase_jwt_secret == ""
    assert await get_owner_id(authorization=None) == "ramesh"


@pytest.mark.db
async def test_requests_need_token_when_secret_set(session, monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    await seed(session)
    async with _client(session) as client:
        assert (await client.get("/buyers")).status_code == 401
        bad = _token("ramesh", secret="wrong-secret")
        assert (await client.get("/buyers", headers=bad)).status_code == 401
        ok = (await client.get("/buyers", headers=_token("ramesh")))
        assert ok.status_code == 200
        assert len(ok.json()) == 5


@pytest.mark.db
async def test_owner_cannot_read_other_owners_data(session, monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    await seed(session)
    await _seed_second_owner(session)
    async with _client(session) as client:
        meera = _token("meera")
        buyers = (await client.get("/buyers", headers=meera)).json()
        assert [b["id"] for b in buyers] == ["chennai-silks"]

        # ramesh's buyer is invisible to meera — detail and run-cycle both 404
        assert (await client.get("/buyers/anand", headers=meera)).status_code == 404
        assert (await client.post("/buyers/anand/run-cycle",
                                  headers=meera)).status_code == 404

        # cash events: meera has none; toggling ramesh's event is a 404
        cal = (await client.get("/cash-calendar", headers=meera)).json()
        assert cal["days"] == [] and cal["week"] == []
        assert (await client.post("/cash-events/ce1/toggle",
                                  headers=meera)).status_code == 404


@pytest.mark.db
async def test_vector_memory_is_owner_namespaced(session):
    from app.retrieval.embedder import StubEmbedder
    from app.retrieval.vector_store import PgVectorStore

    await seed(session)
    await _seed_second_owner(session)
    store_a = PgVectorStore(session, StubEmbedder(), owner_id="ramesh")
    await store_a.add("anand", "firm tone worked at day 10")
    await session.commit()

    hits_a = await store_a.search("anand", "what worked")
    assert hits_a == ["firm tone worked at day 10"]
    # same buyer_id queried under another owner's namespace finds nothing
    store_b = PgVectorStore(session, StubEmbedder(), owner_id="meera")
    assert await store_b.search("anand", "what worked") == []


@pytest.mark.db
@pytest.mark.redis
async def test_queue_is_owner_namespaced_via_api(session, monkeypatch):
    from app.queue.redis_queue import RedisUrgencyQueue

    try:
        q = RedisUrgencyQueue()
        q._r.ping()
    except Exception:
        pytest.skip("redis not available")

    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    await seed(session)
    await _seed_second_owner(session)
    q.clear(owner_id="ramesh")
    q.clear(owner_id="meera")
    q.push("anand", 0.9, "inv-anand", "2026-05-04", owner_id="ramesh")
    try:
        async with _client(session) as client:
            mine = (await client.get("/queue", headers=_token("ramesh"))).json()
            theirs = (await client.get("/queue", headers=_token("meera"))).json()
            assert mine["size"] == 1
            assert theirs["size"] == 0
    finally:
        q.clear(owner_id="ramesh")
