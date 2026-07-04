import json

from app.channels.base import Channel, DispatchResult
from app.channels.simulated import SimulatedChannel
from app.config import settings


def _lookup(raw: str) -> dict[str, str]:
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {}


class RoutingChannel:
    """Routes per channel_kind: email -> SMTP, anything else -> Twilio."""

    def __init__(self, twilio: Channel | None = None, email: Channel | None = None,
                 fallback: Channel | None = None):
        self._twilio = twilio
        self._email = email
        self._fallback = fallback or SimulatedChannel()

    def send(self, *, buyer_id: str, message: str, channel_kind: str) -> DispatchResult:
        kind = (channel_kind or "").lower()
        ch = self._email if "email" in kind else self._twilio
        return (ch or self._fallback).send(
            buyer_id=buyer_id, message=message, channel_kind=channel_kind)


def get_channel() -> Channel:
    """Env-driven channel selection. Without any credentials this returns
    SimulatedChannel, so tests and the demo run with zero external setup."""
    twilio = email = None
    if settings.twilio_account_sid and settings.twilio_auth_token:
        from app.channels.twilio_channel import TwilioChannel
        twilio = TwilioChannel(to_lookup=_lookup(settings.twilio_to_map))
    if settings.smtp_host:
        from app.channels.email_channel import EmailChannel
        email = EmailChannel(to_lookup=_lookup(settings.email_to_map))
    if twilio is None and email is None:
        return SimulatedChannel()
    return RoutingChannel(twilio=twilio, email=email)
