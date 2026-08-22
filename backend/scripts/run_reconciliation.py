"""AI Finance Controller demo: run the reconciliation loop end-to-end over a
synthetic bank-vs-ledger batch and report throughput, match rate, and every
unresolved exception.

    USE_STUB_LLM=1 python scripts/run_reconciliation.py
    ANTHROPIC_API_KEY=... USE_STUB_LLM=0 python scripts/run_reconciliation.py
"""
import argparse
import json
from pathlib import Path

from app.agents.reconciliation import ReconciliationAgent, ReconciliationController
from app.config import settings
from app.data.synthetic_reconciliation import generate
from app.llm.anthropic_client import AnthropicClient
from app.llm.stub import StubLLM
from app.services.reconciliation import ReconciliationEngine


def _build_llm():
    if settings.use_stub_llm or not settings.anthropic_api_key:
        # No structured_response configured: every ambiguous case the rules
        # engine hands off raises LLMError, which the agent turns into an
        # honest "agent_uncertain" exception rather than a guessed match.
        return StubLLM(raise_error=True)
    return AnthropicClient()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n", type=int, default=40,
                        help="number of underlying transactions to synthesize")
    parser.add_argument("--out", type=str, default=None,
                        help="path to write the JSON report (default: reports/reconciliation_report.json)")
    args = parser.parse_args()

    bank, ledger = generate(seed=args.seed, n_transactions=args.n)
    llm = _build_llm()
    controller = ReconciliationController(ReconciliationEngine(), ReconciliationAgent(llm))
    report = controller.run(bank, ledger)

    print(f"AI Finance Controller — reconciliation run (seed={args.seed})")
    print(f"  bank records:    {report.total_bank}")
    print(f"  ledger records:  {report.total_ledger}")
    print(f"  matched pairs:   {report.matched_count}")
    print(f"  match rate:      {report.match_rate_bank:.1%} of bank records, "
          f"{report.match_rate_ledger:.1%} of ledger records")
    print(f"  throughput:      {report.elapsed_seconds:.3f}s total, "
          f"{report.records_per_second:.1f} records/sec")
    print(f"  exceptions:      {len(report.exceptions)} (see below)")
    if isinstance(llm, StubLLM):
        print("  note: USE_STUB_LLM active — ambiguous cases resolve to honest exceptions.")
        print("        Set ANTHROPIC_API_KEY and USE_STUB_LLM=0 for live agent adjudication.")

    by_method: dict[str, int] = {}
    for p in report.matched_pairs:
        by_method[p.method] = by_method.get(p.method, 0) + 1
    print("\n  matches by method:")
    for method, count in sorted(by_method.items(), key=lambda kv: -kv[1]):
        print(f"    {method:<20} {count}")

    if report.exceptions:
        print("\n  exceptions (unresolved — nothing silently dropped):")
        for e in report.exceptions:
            print(f"    [{e.side:6}] {e.record_id:8} {e.reason:22} {e.detail}")

    out_path = Path(args.out) if args.out else (
        Path(__file__).resolve().parent.parent / "reports" / "reconciliation_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json")
    payload.update(
        matched_count=report.matched_count,
        match_rate_bank=report.match_rate_bank,
        match_rate_ledger=report.match_rate_ledger,
        records_per_second=report.records_per_second,
    )
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"\n  full report written to {out_path}")


if __name__ == "__main__":
    main()
