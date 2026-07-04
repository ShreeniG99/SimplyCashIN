import pytest
from httpx import ASGITransport, AsyncClient

from app.api.app import create_app
from app.config import settings
from app.db.seed import seed
from app.db.session import get_session


def _client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.db
async def test_webhook_appends_buyer_turn(session):
    await seed(session)
    async with _client(session) as client:
        res = await client.post("/webhooks/twilio?buyer_id=anand",
                                data={"From": "whatsapp:+919800", "Body": "Paying tomorrow"})
        assert res.status_code == 200
        assert res.json()["status"] == "recorded"

        thread = (await client.get("/buyers/anand")).json()["thread"]
        assert thread[-1]["sender"] == "buyer"
        assert thread[-1]["text"] == "Paying tomorrow"


@pytest.mark.db
async def test_webhook_unknown_buyer_is_404(session):
    await seed(session)
    async with _client(session) as client:
        res = await client.post("/webhooks/twilio?buyer_id=ghost",
                                data={"Body": "hello"})
        assert res.status_code == 404


@pytest.mark.db
async def test_webhook_without_mapping_is_ignored(session):
    await seed(session)
    async with _client(session) as client:
        res = await client.post("/webhooks/twilio", data={"Body": "hello"})
        assert res.status_code == 200
        assert res.json()["status"] == "ignored"


@pytest.mark.db
async def test_webhook_signature_check_behind_flag(session, monkeypatch):
    await seed(session)
    monkeypatch.setattr(settings, "twilio_validate_signature", True)
    async with _client(session) as client:
        res = await client.post("/webhooks/twilio?buyer_id=anand",
                                data={"Body": "hi"})
        assert res.status_code == 403

        res = await client.post("/webhooks/twilio?buyer_id=anand",
                                data={"Body": "hi"},
                                headers={"X-Twilio-Signature": "stub"})
        assert res.status_code == 200
