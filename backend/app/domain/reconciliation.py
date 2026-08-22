import datetime as dt
from typing import Literal

from pydantic import BaseModel

MatchMethod = Literal[
    "exact_reference", "exact_amount_date", "amount_date_window",
    "fuzzy_description", "agent_adjudicated",
]

ExceptionReason = Literal[
    "no_candidate", "ambiguous_candidates", "agent_rejected", "agent_uncertain",
]


class BankTransaction(BaseModel):
    """One row from the bank statement source."""
    id: str
    date: dt.date
    amount_paise: int
    description: str
    counterparty: str
    reference: str | None = None


class LedgerEntry(BaseModel):
    """One row from the internal (books) ledger source."""
    id: str
    date: dt.date
    amount_paise: int
    description: str
    counterparty: str
    reference: str | None = None
    invoice_id: str | None = None


class MatchedPair(BaseModel):
    bank_id: str
    ledger_id: str
    method: MatchMethod
    confidence: float
    notes: str = ""


class ReconciliationException(BaseModel):
    side: Literal["bank", "ledger"]
    record_id: str
    reason: ExceptionReason
    detail: str
    candidate_ids: list[str] = []


class ReconciliationReport(BaseModel):
    total_bank: int
    total_ledger: int
    matched_pairs: list[MatchedPair]
    exceptions: list[ReconciliationException]
    elapsed_seconds: float

    @property
    def matched_count(self) -> int:
        return len(self.matched_pairs)

    @property
    def match_rate_bank(self) -> float:
        return self.matched_count / self.total_bank if self.total_bank else 0.0

    @property
    def match_rate_ledger(self) -> float:
        return self.matched_count / self.total_ledger if self.total_ledger else 0.0

    @property
    def records_per_second(self) -> float:
        total = self.total_bank + self.total_ledger
        return total / self.elapsed_seconds if self.elapsed_seconds > 0 else float("inf")
