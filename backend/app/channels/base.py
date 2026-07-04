from dataclasses import dataclass
from typing import Protocol


@dataclass
class DispatchResult:
    ok: bool
    detail: str = ""
    # transient=True marks failures worth retrying (network blip, provider 5xx);
    # permanent failures (no contact on file) go straight to escalation.
    transient: bool = False


class Channel(Protocol):
    def send(self, *, buyer_id: str, message: str, channel_kind: str) -> DispatchResult: ...
