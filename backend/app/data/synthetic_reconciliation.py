"""Deterministic synthetic bank-statement / ledger pair for the
reconciliation demo. Seeded — the same seed always produces the same batch,
so the match rate reported by scripts/run_reconciliation.py and asserted in
tests/test_reconciliation_e2e.py is reproducible, not cherry-picked."""

import datetime as dt
import random

from app.domain.reconciliation import BankTransaction, LedgerEntry

_COUNTERPARTIES = [
    "Anand Motors", "Priya Textiles", "Rajan Auto Parts", "Sundar Traders",
    "Meera Exports", "Kavin Logistics", "Deepa Fabrics", "Ganesh Hardware",
    "Lakshmi Foods", "Vikram Steel", "Nithya Chemicals", "Suresh Electricals",
]

_DESC_TEMPLATES = [
    "NEFT payment {inv}", "UPI/{cp}/{inv}", "RTGS credit {cp}",
    "Cheque clearing {inv}", "IMPS transfer {cp} {inv}", "Payment received {inv}",
]

_ORPHAN_BANK_DESCRIPTIONS = [
    "Bank charges", "Interest credit", "Unidentified NEFT credit", "GST refund",
]

_BASE_DATE = dt.date(2026, 8, 1)


def _noisy_description(template: str, cp: str, inv: str, rng: random.Random) -> str:
    text = template.format(cp=cp, inv=inv)
    if rng.random() < 0.5:
        text = text.replace("payment", "pymt").replace("Payment", "Pymt")
    if rng.random() < 0.3:
        text = f"{text} {rng.choice(['ref', 'txn'])}"
    return text


def generate(seed: int = 42, n_transactions: int = 40
             ) -> tuple[list[BankTransaction], list[LedgerEntry]]:
    """Generate a batch spanning every reconciliation case the engine and
    agent need to handle: clean exact matches, settlement lag, rounding +
    description drift, bank-only orphans, ledger-only orphans, and genuinely
    ambiguous duplicate-invoice pairs."""
    rng = random.Random(seed)
    bank: list[BankTransaction] = []
    ledger: list[LedgerEntry] = []

    for i in range(n_transactions):
        cp = rng.choice(_COUNTERPARTIES)
        inv = f"INV{1000 + i}"
        amount = rng.randint(5_000, 250_000) * 100  # whole-rupee amounts, in paise
        txn_date = _BASE_DATE + dt.timedelta(days=rng.randint(0, 20))
        desc_template = rng.choice(_DESC_TEMPLATES)
        bank_id, ledger_id = f"BNK{i:03d}", f"LED{i:03d}"
        reference = f"REF{20000 + i}"

        roll = rng.random()
        if roll < 0.40:  # clean: matching reference, same amount and date
            bank.append(BankTransaction(
                id=bank_id, date=txn_date, amount_paise=amount,
                description=_noisy_description(desc_template, cp, inv, rng),
                counterparty=cp, reference=reference))
            ledger.append(LedgerEntry(
                id=ledger_id, date=txn_date, amount_paise=amount,
                description=f"{cp} settlement {inv}", counterparty=cp,
                reference=reference, invoice_id=inv))

        elif roll < 0.60:  # settlement lag: ledger booked 1-3 days before bank clears
            lag = rng.randint(1, 3)
            bank.append(BankTransaction(
                id=bank_id, date=txn_date, amount_paise=amount,
                description=_noisy_description(desc_template, cp, inv, rng),
                counterparty=cp, reference=None))
            ledger.append(LedgerEntry(
                id=ledger_id, date=txn_date - dt.timedelta(days=lag), amount_paise=amount,
                description=f"{cp} invoice {inv}", counterparty=cp,
                reference=None, invoice_id=inv))

        elif roll < 0.75:  # rounding noise + reworded description
            drift = rng.choice([-50, -25, 25, 50])
            bank.append(BankTransaction(
                id=bank_id, date=txn_date, amount_paise=amount + drift,
                description=_noisy_description(desc_template, cp, inv, rng),
                counterparty=cp, reference=None))
            ledger.append(LedgerEntry(
                id=ledger_id, date=txn_date + dt.timedelta(days=rng.choice([-2, -1, 1, 2])),
                amount_paise=amount, description=f"Being amt recd from {cp} {inv}",
                counterparty=cp, reference=None, invoice_id=inv))

        elif roll < 0.85:  # bank-only orphan — no ledger counterpart at all
            bank.append(BankTransaction(
                id=bank_id, date=txn_date, amount_paise=rng.randint(50, 5_000) * 100,
                description=rng.choice(_ORPHAN_BANK_DESCRIPTIONS),
                counterparty="Bank", reference=None))

        elif roll < 0.95:  # ledger-only orphan — booked, not yet cleared
            ledger.append(LedgerEntry(
                id=ledger_id, date=txn_date, amount_paise=amount,
                description=f"Accrued receivable {cp} {inv}", counterparty=cp,
                reference=None, invoice_id=inv))

        else:  # genuinely ambiguous: one settlement, two open invoices it could cover.
            # Half the time the bank memo happens to name the right invoice —
            # invisible to the rules engine (which never reads free text this
            # deeply) but exactly the kind of clue an LLM adjudicator should
            # pick up on; the other half there is truly no signal, and an
            # honest agent must decline rather than guess.
            hinted = rng.random() < 0.5
            bank_desc = (f"NEFT payment received from {cp} against {inv}" if hinted
                        else f"NEFT payment received from {cp}")
            bank.append(BankTransaction(
                id=bank_id, date=txn_date, amount_paise=amount,
                description=bank_desc,
                counterparty=cp, reference=None))
            ledger.append(LedgerEntry(
                id=f"{ledger_id}A", date=txn_date, amount_paise=amount,
                description=f"{cp} settlement {inv}", counterparty=cp,
                reference=None, invoice_id=inv))
            ledger.append(LedgerEntry(
                id=f"{ledger_id}B", date=txn_date, amount_paise=amount,
                description=f"{cp} settlement INV{1000 + i}-B", counterparty=cp,
                reference=None, invoice_id=f"{inv}-B"))

    return bank, ledger
