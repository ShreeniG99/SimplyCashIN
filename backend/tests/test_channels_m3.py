from app.channels.base import DispatchResult
from app.channels.email_channel import EmailChannel
from app.channels.factory import RoutingChannel, get_channel
from app.channels.retry import RetryingChannel
from app.channels.simulated import SimulatedChannel
from app.channels.twilio_channel import TwilioChannel
from app.config import settings


class _FakeMessages:
    def __init__(self, fail: Exception | None = None):
        self.fail = fail
        self.created: list[dict] = []

    def create(self, **kw):
        if self.fail:
            raise self.fail
        self.created.append(kw)

        class _Msg:
            sid = "SM123"
        return _Msg()


class _FakeTwilio:
    def __init__(self, fail: Exception | None = None):
        self.messages = _FakeMessages(fail)


def test_twilio_whatsapp_prefixes_numbers():
    client = _FakeTwilio()
    ch = TwilioChannel(client, whatsapp_from="+1415000", sms_from="+1415111",
                       to_lookup={"anand": "+9198000"})
    result = ch.send(buyer_id="anand", message="Namaste", channel_kind="WhatsApp Business")
    assert result.ok is True
    sent = client.messages.created[0]
    assert sent["to"] == "whatsapp:+9198000"
    assert sent["from_"] == "whatsapp:+1415000"
    assert sent["body"] == "Namaste"


def test_twilio_sms_uses_plain_numbers():
    client = _FakeTwilio()
    ch = TwilioChannel(client, whatsapp_from="+1415000", sms_from="+1415111",
                       to_lookup={"anand": "+9198000"})
    result = ch.send(buyer_id="anand", message="Reminder", channel_kind="SMS")
    assert result.ok is True
    assert client.messages.created[0]["to"] == "+9198000"
    assert client.messages.created[0]["from_"] == "+1415111"


def test_twilio_no_phone_is_permanent_failure():
    ch = TwilioChannel(_FakeTwilio(), to_lookup={})
    result = ch.send(buyer_id="anand", message="x", channel_kind="SMS")
    assert result.ok is False
    assert result.transient is False


def test_twilio_provider_error_is_transient():
    ch = TwilioChannel(_FakeTwilio(fail=ConnectionError("boom")),
                       to_lookup={"anand": "+9198000"})
    result = ch.send(buyer_id="anand", message="x", channel_kind="SMS")
    assert result.ok is False
    assert result.transient is True


def test_email_channel_sends_via_injected_transport():
    sent = []

    async def fake_send(msg):
        sent.append(msg)

    ch = EmailChannel(fake_send, from_addr="scin@example.com",
                      to_lookup={"anand": "anand@example.com"})
    result = ch.send(buyer_id="anand", message="Payment due", channel_kind="Email")
    assert result.ok is True
    assert sent[0]["To"] == "anand@example.com"
    assert "Payment due" in sent[0].get_content()


def test_email_channel_missing_address_is_permanent():
    async def fake_send(msg):  # pragma: no cover
        raise AssertionError("must not send")

    ch = EmailChannel(fake_send, to_lookup={})
    result = ch.send(buyer_id="anand", message="x", channel_kind="Email")
    assert result.ok is False
    assert result.transient is False


def test_email_channel_smtp_error_is_transient():
    async def fake_send(msg):
        raise ConnectionError("smtp down")

    ch = EmailChannel(fake_send, to_lookup={"anand": "a@b.c"})
    result = ch.send(buyer_id="anand", message="x", channel_kind="Email")
    assert result.ok is False
    assert result.transient is True


def test_factory_returns_simulated_without_creds():
    assert isinstance(get_channel(), SimulatedChannel)


def test_factory_returns_routing_with_twilio_creds(monkeypatch):
    monkeypatch.setattr(settings, "twilio_account_sid", "AC123")
    monkeypatch.setattr(settings, "twilio_auth_token", "tok")
    ch = get_channel()
    assert isinstance(ch, RoutingChannel)


def test_routing_channel_picks_email_for_email_kind():
    twilio, email = SimulatedChannel(), SimulatedChannel()
    ch = RoutingChannel(twilio=twilio, email=email)
    ch.send(buyer_id="a", message="m", channel_kind="Email")
    ch.send(buyer_id="a", message="m", channel_kind="WhatsApp Business")
    assert len(email.sent) == 1
    assert len(twilio.sent) == 1


class _Flaky:
    def __init__(self, failures: int, transient: bool = True):
        self.failures = failures
        self.transient = transient
        self.calls = 0

    def send(self, *, buyer_id, message, channel_kind):
        self.calls += 1
        if self.calls <= self.failures:
            return DispatchResult(ok=False, detail="blip", transient=self.transient)
        return DispatchResult(ok=True, detail="sent")


def test_retrying_channel_recovers_from_transient_failures():
    naps = []
    inner = _Flaky(failures=2)
    ch = RetryingChannel(inner, retries=3, backoff_base=0.5, sleep=naps.append)
    result = ch.send(buyer_id="a", message="m", channel_kind="SMS")
    assert result.ok is True
    assert inner.calls == 3
    assert naps == [0.5, 1.0]  # exponential backoff


def test_retrying_channel_exhausts_then_reports_failure():
    inner = _Flaky(failures=10)
    ch = RetryingChannel(inner, retries=3, sleep=lambda _: None)
    result = ch.send(buyer_id="a", message="m", channel_kind="SMS")
    assert result.ok is False
    assert inner.calls == 3


def test_retrying_channel_does_not_retry_permanent_failure():
    inner = _Flaky(failures=10, transient=False)
    ch = RetryingChannel(inner, retries=3, sleep=lambda _: None)
    result = ch.send(buyer_id="a", message="m", channel_kind="SMS")
    assert result.ok is False
    assert inner.calls == 1
