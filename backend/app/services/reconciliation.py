from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.domain.reconciliation import BankTransaction, LedgerEntry, MatchedPair, MatchMethod

# Tier thresholds — looser at each step; a tier only claims a bank record
# when exactly one ledger candidate satisfies it (see EngineResult.ambiguous).
_EXACT_DATE_WINDOW_DAYS = 3
_FUZZY_DATE_WINDOW_DAYS = 5
_FUZZY_AMOUNT_TOLERANCE_PAISE = 100  # rupee-rounding / paisa-drop slop
_FUZZY_DESCRIPTION_THRESHOLD = 0.45


def _description_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


_TIERS: list[tuple[MatchMethod, float]] = [
    ("exact_reference", 1.0),
    ("exact_amount_date", 0.97),
    ("amount_date_window", 0.9),
    ("fuzzy_description", 0.7),
]


def _predicate(method: MatchMethod, b: BankTransaction, l: LedgerEntry) -> bool:
    if method == "exact_reference":
        return bool(b.reference) and b.reference == l.reference and b.amount_paise == l.amount_paise
    if method == "exact_amount_date":
        return b.amount_paise == l.amount_paise and b.date == l.date
    if method == "amount_date_window":
        return (b.amount_paise == l.amount_paise
                and abs((b.date - l.date).days) <= _EXACT_DATE_WINDOW_DAYS)
    if method == "fuzzy_description":
        if not (abs(b.amount_paise - l.amount_paise) <= _FUZZY_AMOUNT_TOLERANCE_PAISE
                and abs((b.date - l.date).days) <= _FUZZY_DATE_WINDOW_DAYS):
            return False
        same_counterparty = b.counterparty.strip().lower() == l.counterparty.strip().lower()
        similar_description = _description_similarity(b.description, l.description) >= _FUZZY_DESCRIPTION_THRESHOLD
        return same_counterparty or similar_description
    raise ValueError(f"unknown tier {method}")


@dataclass
class EngineResult:
    pairs: list[MatchedPair]
    unmatched_bank: list[BankTransaction]
    unmatched_ledger: list[LedgerEntry]
    # bank records with >1 plausible ledger candidate at the tier where the
    # ambiguity was found — handed to the LLM agent, never silently guessed.
    ambiguous: dict[str, list[LedgerEntry]] = field(default_factory=dict)


class ReconciliationEngine:
    """Deterministic, tiered matcher. Never calls an LLM and never breaks a
    tie itself — a bank record with more than one plausible ledger candidate
    at a given tier is reported as ambiguous rather than guessed at."""

    def match(self, bank: list[BankTransaction], ledger: list[LedgerEntry]) -> EngineResult:
        remaining_bank = {b.id: b for b in bank}
        remaining_ledger = {l.id: l for l in ledger}
        pairs: list[MatchedPair] = []
        ambiguous: dict[str, list[LedgerEntry]] = {}

        for method, confidence in _TIERS:
            for bank_id in [bid for bid in remaining_bank if bid not in ambiguous]:
                b = remaining_bank[bank_id]
                candidates = [l for l in remaining_ledger.values() if _predicate(method, b, l)]
                if len(candidates) == 1:
                    l = candidates[0]
                    pairs.append(MatchedPair(bank_id=b.id, ledger_id=l.id,
                                             method=method, confidence=confidence))
                    del remaining_bank[bank_id]
                    del remaining_ledger[l.id]
                elif len(candidates) > 1:
                    ambiguous[bank_id] = candidates

        for bank_id in ambiguous:
            remaining_bank.pop(bank_id, None)

        return EngineResult(
            pairs=pairs,
            unmatched_bank=list(remaining_bank.values()),
            unmatched_ledger=list(remaining_ledger.values()),
            ambiguous=ambiguous,
        )
