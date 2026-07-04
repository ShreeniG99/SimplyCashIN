import datetime as dt
import re
import uuid

from app.domain.enums import InvoiceStatus
from app.domain.models import Buyer, Invoice


class WhatsAppConnector:
    """Parses exported WhatsApp chat .txt files.
    Extracts buyer name from contact and payment mentions."""

    # Requires an explicit currency marker (₹, Rs, Rs., INR) so bare numbers,
    # phone numbers, and words ending in r/s never read as amounts.
    _AMOUNT_RE = re.compile(r"(?:₹|\brs\.?|\binr\b)\s*([\d][\d,]*)", re.IGNORECASE)
    _DATE_RE = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})")

    def parse(self, raw: bytes, owner_id: str) -> list[tuple[Buyer, Invoice]]:
        text = raw.decode("utf-8")
        lines = text.splitlines()
        out: list[tuple[Buyer, Invoice]] = []

        # First line often contains the contact name: "+91 98765... (Anand Motors)"
        contact_name = "Unknown Buyer"
        for line in lines[:5]:
            if m := re.search(r"\(([^)]+)\)", line):
                contact_name = m.group(1)
                break

        # Scan for payment mentions
        for line in lines:
            amounts = self._extract_amounts(line)
            dates = self._extract_dates(line)
            if amounts:
                buyer = Buyer(
                    id=str(uuid.uuid4()),
                    owner_id=owner_id,
                    name=contact_name,
                    tier="Inferred from chat",
                    relationship_years=0.0,
                    on_time_rate=0.5,
                    preferred_channel="WhatsApp Business",
                )
                due = dates[0] if dates else dt.date(2026, 5, 18)
                invoice = Invoice(
                    id=str(uuid.uuid4()),
                    buyer_id=buyer.id,
                    number=f"WA-{buyer.id[:8]}",
                    amount_paise=amounts[0],
                    due_date=due,
                    status=InvoiceStatus.OVERDUE,
                    days_overdue=max(0, (dt.date(2026, 5, 18) - due).days),
                )
                out.append((buyer, invoice))
                break  # one invoice per chat for now
        return out

    def _extract_amounts(self, text: str) -> list[int]:
        amounts: list[int] = []
        for m in self._AMOUNT_RE.finditer(text):
            num_str = m.group(1)
            if num_str:
                num = int(num_str.replace(",", ""))
                if num > 100:  # likely meaningful
                    amounts.append(num * 100)  # rupees → paise
        return amounts

    def _extract_dates(self, text: str) -> list[dt.date]:
        dates: list[dt.date] = []
        for m in self._DATE_RE.finditer(text):
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if year < 100:
                year += 2000
            try:
                dates.append(dt.date(year, month, day))
            except ValueError:
                pass
        return dates
