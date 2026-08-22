import datetime as dt

from app.agents.reconciliation import AdjudicationOut, ReconciliationAgent
from app.domain.reconciliation import BankTransaction, LedgerEntry
from app.llm.stub import StubLLM

D = dt.date(2026, 8, 10)
BANK = BankTransaction(id="B1", date=D, amount_paise=100_00, description="NEFT payment",
                       counterparty="Acme", reference=None)
CAND_A = LedgerEntry(id="LA", date=D, amount_paise=100_00, description="Acme settlement INV1",
                     counterparty="Acme", reference=None, invoice_id="INV1")
CAND_B = LedgerEntry(id="LB", date=D, amount_paise=100_00, description="Acme settlement INV2",
                     counterparty="Acme", reference=None, invoice_id="INV2")


def test_confident_match_is_accepted():
    llm = StubLLM(structured_response=AdjudicationOut(
        matched_ledger_id="LA", confidence=0.9, reasoning="invoice number matches"))
    result = ReconciliationAgent(llm).adjudicate(BANK, [CAND_A, CAND_B])
    assert result.status == "matched"
    assert result.matched_ledger_id == "LA"


def test_explicit_no_match_is_rejected_not_forced():
    llm = StubLLM(structured_response=AdjudicationOut(
        matched_ledger_id=None, confidence=0.9, reasoning="neither invoice lines up"))
    result = ReconciliationAgent(llm).adjudicate(BANK, [CAND_A, CAND_B])
    assert result.status == "rejected"
    assert result.matched_ledger_id is None


def test_low_confidence_match_is_downgraded_to_uncertain():
    llm = StubLLM(structured_response=AdjudicationOut(
        matched_ledger_id="LA", confidence=0.2, reasoning="might be LA, not sure"))
    result = ReconciliationAgent(llm, min_confidence=0.6).adjudicate(BANK, [CAND_A, CAND_B])
    assert result.status == "low_confidence"
    assert result.matched_ledger_id is None


def test_id_outside_candidate_set_is_rejected():
    llm = StubLLM(structured_response=AdjudicationOut(
        matched_ledger_id="NOT_A_CANDIDATE", confidence=0.9, reasoning="hallucinated id"))
    result = ReconciliationAgent(llm).adjudicate(BANK, [CAND_A, CAND_B])
    assert result.status == "rejected"


def test_llm_error_surfaces_as_error_status_not_a_crash():
    llm = StubLLM(raise_error=True)
    result = ReconciliationAgent(llm).adjudicate(BANK, [CAND_A, CAND_B])
    assert result.status == "error"
    assert result.matched_ledger_id is None
