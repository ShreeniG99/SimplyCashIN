from dataclasses import dataclass
from typing import Protocol


@dataclass
class DispatchResult:
    ok: bool
    detail: str = ""


class Channel(Protocol):
    def send(self, *, buyer_id: str, message: str, channel_kind: str) -> DispatchResult: ...
