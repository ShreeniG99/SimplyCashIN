from app.channels.base import DispatchResult
from app.config import settings


class TwilioChannel:
    """WhatsApp + SMS via the Twilio REST API.

    The buyer table carries no phone number yet, so destinations come from
    `to_lookup` (factory fills it from TWILIO_TO_MAP). A missing entry is a
    permanent failure -> escalation; a provider error is transient -> retryable.
    """

    def __init__(self, client=None, *, whatsapp_from: str | None = None,
                 sms_from: str | None = None, to_lookup: dict[str, str] | None = None):
        if client is None:
            from twilio.rest import Client
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self._client = client
        self._wa_from = whatsapp_from or settings.twilio_whatsapp_from
        self._sms_from = sms_from or settings.twilio_sms_from
        self._to = to_lookup or {}

    def send(self, *, buyer_id: str, message: str, channel_kind: str) -> DispatchResult:
        to = self._to.get(buyer_id)
        if not to:
            return DispatchResult(ok=False, detail=f"no phone on file for {buyer_id}")
        if "whatsapp" in (channel_kind or "").lower():
            from_, to_ = f"whatsapp:{self._wa_from}", f"whatsapp:{to}"
        else:
            from_, to_ = self._sms_from, to
        try:
            msg = self._client.messages.create(to=to_, from_=from_, body=message)
        except Exception as exc:  # noqa: BLE001 — provider/network errors are retryable
            return DispatchResult(ok=False, detail=f"twilio error: {exc}", transient=True)
        return DispatchResult(ok=True, detail=f"twilio sid {msg.sid}")
