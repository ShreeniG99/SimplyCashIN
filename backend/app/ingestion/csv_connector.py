import csv
import datetime as dt
import io
import uuid

from app.domain.enums import InvoiceStatus
from app.domain.models import Buyer, Invoice


class CSVConnector:
    """Parses CSV with columns: buyer_name, buyer_tier, relationship_years,
    on_time_rate, preferred_channel, invoice_number, amount_rupees, due_date, status.
    Amount rupees → paise (×100). status is optional (default: 'overdue')."""

    def parse(self, raw: bytes, owner_id: str) -> list[tuple[Buyer, Invoice]]:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
        out: list[tuple[Buyer, Invoice]] = []
        for row in reader:
            buyer = Buyer(
                id=str(uuid.uuid4()),
                owner_id=owner_id,
                name=row["buyer_name"],
                tier=row["buyer_tier"],
                relationship_years=float(row["relationship_years"]),
                on_time_rate=float(row["on_time_rate"]),
                preferred_channel=row["preferred_channel"],
            )
            amount_paise = int(float(row["amount_rupees"]) * 100)
            due_date = dt.date.fromisoformat(row["due_date"])
            days_overdue = (dt.date(2026, 5, 18) - due_date).days
            status_str = row.get("status", "overdue")

            invoice = Invoice(
                id=str(uuid.uuid4()),
                buyer_id=buyer.id,
                number=row["invoice_number"],
                amount_paise=amount_paise,
                due_date=due_date,
                status=InvoiceStatus(status_str),
                days_overdue=max(0, days_overdue),
            )
            out.append((buyer, invoice))
        return out
