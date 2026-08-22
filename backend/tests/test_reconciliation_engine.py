import datetime as dt

from app.domain.reconciliation import BankTransaction, LedgerEntry
from app.services.reconciliation import ReconciliationEngine

D = dt.date(2026, 8, 10)


def _bank(id="B1", date=D, amount=100_00, desc="NEFT payment INV1", cp="Acme", ref="REF1"):
    return BankTransaction(id=id, date=date, amount_paise=amount, description=desc,
                           counterparty=cp, reference=ref)


def _ledger(id="L1", date=D, amount=100_00, desc="Acme settlement INV1", cp="Acme",
            ref="REF1", invoice_id="INV1"):
    return LedgerEntry(id=id, date=date, amount_paise=amount, description=desc,
                       counterparty=cp, reference=ref, invoice_id=invoice_id)


def test_exact_reference_match():
    result = ReconciliationEngine().match([_bank()], [_ledger()])
    assert len(result.pairs) == 1
    assert result.pairs[0].method == "exact_reference"
    assert result.pairs[0].confidence == 1.0
    assert not result.unmatched_bank and not result.unmatched_ledger


def test_amount_date_window_match_without_reference():
    bank = _bank(ref=None, date=D)
    ledger = _ledger(ref=None, date=D - dt.timedelta(days=2))
    result = ReconciliationEngine().match([bank], [ledger])
    assert len(result.pairs) == 1
    assert result.pairs[0].method == "amount_date_window"


def test_date_beyond_window_does_not_match():
    bank = _bank(ref=None, date=D)
    ledger = _ledger(ref=None, date=D - dt.timedelta(days=10))
    result = ReconciliationEngine().match([bank], [ledger])
    assert not result.pairs
    assert result.unmatched_bank and result.unmatched_ledger


def test_fuzzy_description_matches_on_rounding_and_similar_text():
    bank = _bank(ref=None, amount=100_25, desc="IMPS transfer Acme INV1")
    ledger = _ledger(ref=None, amount=100_00, desc="Being amt recd from Acme INV1")
    result = ReconciliationEngine().match([bank], [ledger])
    assert len(result.pairs) == 1
    assert result.pairs[0].method == "fuzzy_description"


def test_fuzzy_matches_on_shared_counterparty_even_with_dissimilar_description():
    bank = _bank(ref=None, amount=100_50, desc="Misc credit", cp="Acme")
    ledger = _ledger(ref=None, amount=100_00, desc="Q3 dues", cp="Acme")
    result = ReconciliationEngine().match([bank], [ledger])
    assert len(result.pairs) == 1
    assert result.pairs[0].method == "fuzzy_description"


def test_amount_outside_tolerance_is_an_exception_not_a_guess():
    bank = _bank(ref=None, amount=100_00 + 500)  # way beyond rounding slop
    ledger = _ledger(ref=None, amount=100_00)
    result = ReconciliationEngine().match([bank], [ledger])
    assert not result.pairs
    assert result.unmatched_bank == [bank]
    assert result.unmatched_ledger == [ledger]


def test_multiple_candidates_are_ambiguous_not_guessed():
    bank = _bank(ref=None)
    ledger_a = _ledger(id="LA", ref=None, invoice_id="INV1")
    ledger_b = _ledger(id="LB", ref=None, invoice_id="INV1-B", desc="Acme settlement INV1-B")
    result = ReconciliationEngine().match([bank], [ledger_a, ledger_b])
    assert not result.pairs
    assert bank.id in result.ambiguous
    assert {c.id for c in result.ambiguous[bank.id]} == {"LA", "LB"}
    assert result.unmatched_bank == []  # pulled out for the agent, not reported as a plain orphan


def test_unmatched_records_reported_on_both_sides():
    result = ReconciliationEngine().match(
        [_bank(id="ORPHAN_B", ref=None, amount=999_00)],
        [_ledger(id="ORPHAN_L", ref=None, amount=111_00)])
    assert not result.pairs
    assert [b.id for b in result.unmatched_bank] == ["ORPHAN_B"]
    assert [l.id for l in result.unmatched_ledger] == ["ORPHAN_L"]
