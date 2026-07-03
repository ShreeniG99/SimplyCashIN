from typing import Protocol

from app.domain.models import Buyer, Invoice


class Connector(Protocol):
    """Ingestion connector protocol. Returns list[(Buyer, Invoice)] tuples."""

    def parse(self, raw: bytes, owner_id: str) -> list[tuple[Buyer, Invoice]]: ...
