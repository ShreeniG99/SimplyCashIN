import time
from typing import Literal

from pydantic import BaseModel

from app.domain.reconciliation import (
    BankTransaction, LedgerEntry, MatchedPair, ReconciliationException, ReconciliationReport,
)
from app.llm.base import LLM, LLMError
from app.obs.tracer import NullTracer, Tracer
from app.services.reconciliation import ReconciliationEngine

_SYSTEM = """You are SimplyCashIN's Reconciliation agent. A deterministic rules \
engine matched everything it safely could and handed you ONE bank transaction \
plus the several ledger entries it could not tell apart on rules alone (same \
amount and/or a nearby date, so more than one candidate is plausible). Pick the \
single ledger entry id that is the SAME underlying transaction as the bank \
record, reasoning about realistic noise: settlement lag, rounding, abbreviated \
or reordered descriptions, and counterparty name variants. If none of the \
candidates are plausibly the same transaction — or you cannot tell which one is \
— return matched_ledger_id=null. An honest "no match" beats a guessed one; \
never force a pick to raise the match rate."""


class AdjudicationOut(BaseModel):
    matched_ledger_id: str | None
    confidence: float
    reasoning: str


AdjudicationStatus = Literal["matched", "rejected", "low_confidence", "error"]


class AdjudicationResult(BaseModel):
    bank_id: str
    status: AdjudicationStatus
    matched_ledger_id: str | None
    confidence: float
    reasoning: str


class ReconciliationAgent:
    """LLM-backed adjudicator for the handful of cases the deterministic
    engine could not disambiguate on its own. Behind the same LLM seam as
    the rest of SimplyCashIN — StubLLM in tests, AnthropicClient in prod."""

    def __init__(self, llm: LLM, min_confidence: float = 0.6):
        self.llm = llm
        self.min_confidence = min_confidence

    def adjudicate(self, bank: BankTransaction, candidates: list[LedgerEntry]) -> AdjudicationResult:
        user = self._prompt(bank, candidates)
        try:
            out = self.llm.complete_structured(_SYSTEM, user, AdjudicationOut)
        except LLMError as exc:
            return AdjudicationResult(bank_id=bank.id, status="error", matched_ledger_id=None,
                                      confidence=0.0, reasoning=f"agent call failed: {exc}")

        candidate_ids = {c.id for c in candidates}
        if out.matched_ledger_id is None or out.matched_ledger_id not in candidate_ids:
            return AdjudicationResult(bank_id=bank.id, status="rejected", matched_ledger_id=None,
                                      confidence=out.confidence, reasoning=out.reasoning)
        if out.confidence < self.min_confidence:
            return AdjudicationResult(bank_id=bank.id, status="low_confidence", matched_ledger_id=None,
                                      confidence=out.confidence, reasoning=out.reasoning)
        return AdjudicationResult(bank_id=bank.id, status="matched",
                                  matched_ledger_id=out.matched_ledger_id,
                                  confidence=out.confidence, reasoning=out.reasoning)

    @staticmethod
    def _prompt(bank: BankTransaction, candidates: list[LedgerEntry]) -> str:
        lines = [
            f"Bank transaction {bank.id}: {bank.date} | {bank.amount_paise} paise | "
            f"counterparty={bank.counterparty!r} | desc={bank.description!r} | ref={bank.reference}",
            "Candidate ledger entries (pick one id, or null):",
        ]
        for l in candidates:
            lines.append(
                f"  - {l.id}: {l.date} | {l.amount_paise} paise | "
                f"counterparty={l.counterparty!r} | desc={l.description!r} | "
                f"ref={l.reference} | invoice={l.invoice_id}")
        return "\n".join(lines)


class ReconciliationController:
    """Closes the loop: run the deterministic engine, hand ambiguous
    leftovers to the LLM agent, and produce an honest report — every
    unresolved record ends up in `exceptions` with a reason, never dropped."""

    def __init__(self, engine: ReconciliationEngine, agent: ReconciliationAgent,
                 tracer: Tracer | None = None):
        self.engine = engine
        self.agent = agent
        self.tracer = tracer or NullTracer()

    def run(self, bank: list[BankTransaction], ledger: list[LedgerEntry]) -> ReconciliationReport:
        start = time.perf_counter()
        result = self.engine.match(bank, ledger)
        pairs: list[MatchedPair] = list(result.pairs)
        exceptions: list[ReconciliationException] = []
        claimed_by_agent: set[str] = set()
        bank_by_id = {b.id: b for b in bank}

        for bank_id, candidates in result.ambiguous.items():
            live_candidates = [c for c in candidates if c.id not in claimed_by_agent]
            if not live_candidates:
                exceptions.append(ReconciliationException(
                    side="bank", record_id=bank_id, reason="ambiguous_candidates",
                    detail="every candidate ledger entry was already claimed by another "
                           "bank record with a stronger match",
                    candidate_ids=[c.id for c in candidates]))
                continue

            decision = self.agent.adjudicate(bank_by_id[bank_id], live_candidates)
            self.tracer.trace(
                agent="reconciliation", model="-", prompt=bank_id,
                response=decision.matched_ledger_id or decision.status,
                meta={"status": decision.status, "confidence": decision.confidence})

            if decision.status == "matched":
                pairs.append(MatchedPair(bank_id=bank_id, ledger_id=decision.matched_ledger_id,
                                         method="agent_adjudicated", confidence=decision.confidence,
                                         notes=decision.reasoning))
                claimed_by_agent.add(decision.matched_ledger_id)
            else:
                reason = "agent_rejected" if decision.status == "rejected" else "agent_uncertain"
                exceptions.append(ReconciliationException(
                    side="bank", record_id=bank_id, reason=reason, detail=decision.reasoning,
                    candidate_ids=[c.id for c in candidates]))

        matched_ledger_ids = {p.ledger_id for p in pairs}
        for b in result.unmatched_bank:
            exceptions.append(ReconciliationException(
                side="bank", record_id=b.id, reason="no_candidate",
                detail="no ledger entry within any matching tolerance"))
        for l in result.unmatched_ledger:
            if l.id in matched_ledger_ids:
                continue
            exceptions.append(ReconciliationException(
                side="ledger", record_id=l.id, reason="no_candidate",
                detail="no bank transaction within any matching tolerance"))

        elapsed = time.perf_counter() - start
        return ReconciliationReport(total_bank=len(bank), total_ledger=len(ledger),
                                    matched_pairs=pairs, exceptions=exceptions,
                                    elapsed_seconds=elapsed)
