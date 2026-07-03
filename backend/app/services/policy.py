from app.domain.models import Buyer, CashUrgency, PaymentPlan, Policy, PolicyCheck

CASH_URGENCY_THRESHOLD = 0.5


class PolicyEngine:
    def evaluate(self, plan: PaymentPlan, policy: Policy, urgency: CashUrgency,
                 buyer: Buyer) -> list[PolicyCheck]:
        return [
            PolicyCheck(
                label=f"Within max extension ({policy.max_extension_days}d)",
                value=f"plan needs {plan.extension_days}d",
                ok=plan.extension_days <= policy.max_extension_days,
            ),
            PolicyCheck(
                label=f"Minimum upfront ({policy.min_upfront_pct}%)",
                value=f"plan offers {plan.upfront_pct}%",
                ok=plan.upfront_pct >= policy.min_upfront_pct,
            ),
            PolicyCheck(
                label="Owner cash need this week",
                value=urgency.breaching_need or "no urgent need",
                ok=urgency.score < CASH_URGENCY_THRESHOLD,
            ),
            PolicyCheck(
                label="Relationship tier",
                value=f"{buyer.tier} · {int(buyer.on_time_rate * 100)}% on-time",
                ok=True,
            ),
        ]
