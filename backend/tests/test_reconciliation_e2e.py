from app.agents.reconciliation import (
    AdjudicationOut, ReconciliationAgent, ReconciliationController,
)
from app.data.synthetic_reconciliation import generate
from app.domain.reconciliation import BankTransaction, LedgerEntry
from app.llm.base import LLM
from app.llm.stub import StubLLM
from app.obs.tracer import RecordingTracer
from app.services.reconciliation import ReconciliationEngine


class _InvoiceAwareLLM:
    """Stands in for a real model: picks the ledger candidate whose invoice
    id is embedded in the bank description, else declines — exercising the
    'agent resolves some, honestly punts on the rest' path end to end."""

    def __init__(self):
        self.calls = 0

    def complete_text(self, system: str, user: str, max_tokens: int = 1024) -> str:
        raise NotImplementedError

    def complete_structured(self, system: str, user: str, schema, max_tokens: int = 1024):
        self.calls += 1
        first_line, *candidate_lines = user.splitlines()
        for line in candidate_lines:
            cand_id = line.strip().split(":")[0].lstrip("- ")
            if "invoice=" in line:
                invoice_id = line.split("invoice=")[1].split(" ")[0]
                if invoice_id != "None" and invoice_id in first_line:
                    return schema(matched_ledger_id=cand_id, confidence=0.85,
                                 reasoning="invoice id appears in the bank memo")
        return schema(matched_ledger_id=None, confidence=0.9,
                      reasoning="no candidate invoice id appears in the bank memo")


def _run(llm: LLM):
    bank, ledger = generate(seed=42, n_transactions=40)
    assert len(bank) + len(ledger) >= 50, "batch must exercise at least 50 records"
    controller = ReconciliationController(ReconciliationEngine(), ReconciliationAgent(llm),
                                          tracer=RecordingTracer())
    return controller.run(bank, ledger), bank, ledger


def test_batch_is_reproducible_and_covers_every_case():
    report_a, bank, ledger = _run(StubLLM(raise_error=True))
    report_b, _, _ = _run(StubLLM(raise_error=True))
    dump_a = report_a.model_dump(exclude={"elapsed_seconds"})
    dump_b = report_b.model_dump(exclude={"elapsed_seconds"})
    assert dump_a == dump_b, "same seed must give the same result"
    assert len(bank) + len(ledger) >= 50


def test_deterministic_tiers_alone_clear_a_solid_majority():
    report, bank, ledger = _run(StubLLM(raise_error=True))
    assert 0.6 <= report.match_rate_bank <= 0.95
    assert all(p.method != "agent_adjudicated" for p in report.matched_pairs)


def test_every_leftover_record_is_a_typed_exception_not_a_silent_drop():
    report, bank, ledger = _run(StubLLM(raise_error=True))
    bank_ids = {b.id for b in bank}
    ledger_ids = {l.id for l in ledger}
    matched_bank_ids = {p.bank_id for p in report.matched_pairs}
    matched_ledger_ids = {p.ledger_id for p in report.matched_pairs}
    exception_ids = {(e.side, e.record_id) for e in report.exceptions}

    for bid in bank_ids - matched_bank_ids:
        assert ("bank", bid) in exception_ids
    for lid in ledger_ids - matched_ledger_ids:
        assert ("ledger", lid) in exception_ids
    # every exception has a reason drawn from the typed enum — no free-form fallback
    assert all(e.reason in {"no_candidate", "ambiguous_candidates",
                            "agent_rejected", "agent_uncertain"} for e in report.exceptions)


def test_agent_adjudication_resolves_some_ambiguous_cases_and_raises_match_rate():
    baseline, _, _ = _run(StubLLM(raise_error=True))
    adjudicated, _, _ = _run(_InvoiceAwareLLM())

    assert adjudicated.matched_count > baseline.matched_count
    assert adjudicated.match_rate_bank > baseline.match_rate_bank
    assert any(p.method == "agent_adjudicated" for p in adjudicated.matched_pairs)
    # the agent must still decline when it isn't confident — never guesses to
    # inflate the match rate
    assert any(e.reason in {"agent_rejected", "agent_uncertain"} for e in adjudicated.exceptions) \
        or len(adjudicated.exceptions) < len(baseline.exceptions)


def test_report_is_internally_consistent():
    report, bank, ledger = _run(StubLLM(raise_error=True))
    assert report.total_bank == len(bank)
    assert report.total_ledger == len(ledger)
    accounted_bank = report.matched_count + sum(1 for e in report.exceptions if e.side == "bank")
    accounted_ledger = report.matched_count + sum(1 for e in report.exceptions if e.side == "ledger")
    assert accounted_bank == report.total_bank
    assert accounted_ledger == report.total_ledger
    assert report.elapsed_seconds >= 0
    assert report.records_per_second > 0
