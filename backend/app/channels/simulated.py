from app.channels.base import Channel, DispatchResult


class SimulatedChannel:
    """Records sends instead of calling Twilio/SMTP. Real adapters land in M3."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, *, buyer_id: str, message: str, channel_kind: str) -> DispatchResult:
        self.sent.append({"buyer_id": buyer_id, "message": message, "channel_kind": channel_kind})
        return DispatchResult(ok=True, detail=f"simulated via {channel_kind}")
