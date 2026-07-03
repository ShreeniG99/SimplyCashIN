from app.domain.enums import Tone
from app.domain.models import BuyerContext, CashUrgency, ConversationTurn, DraftMessage
from app.llm.base import LLM
from app.money import format_inr

_SYSTEM = """You are SimplyCashIN's Conversation agent, writing on behalf of an Indian \
MSME owner to a buyer who owes money. Voice: warm, relationship-first, respectful \
Indian-English (e.g. "Namaste Anand ji, hope business is good."). Use the buyer's name. \
Firmness scales with how overdue the payment is and how urgently the owner needs cash, \
but you NEVER threaten and NEVER use collections-agency coldness. Keep it short, plain, \
and human. Output only the message text — no preamble."""


class ConversationAgent:
    def __init__(self, llm: LLM):
        self.llm = llm

    def draft(self, context: BuyerContext, urgency: CashUrgency,
              thread: list[ConversationTurn]) -> DraftMessage:
        firm = context.invoice.days_overdue >= 10 or urgency.score >= 0.5
        tone = Tone.FIRM if firm else Tone.GENTLE
        history = "\n".join(f"{t.sender}: {t.text}" for t in thread[-4:])
        user = (
            f"Buyer: {context.buyer.name} ({context.buyer.tier}), "
            f"{int(context.on_time_rate * 100)}% on-time.\n"
            f"Invoice {context.invoice.number} for {format_inr(context.invoice.amount_paise)}, "
            f"{context.invoice.days_overdue} days overdue.\n"
            f"Owner cash urgency: {urgency.score:.2f}"
            f"{' (' + urgency.breaching_need + ')' if urgency.breaching_need else ''}.\n"
            f"Desired tone: {tone.value}.\n"
            f"Recent conversation:\n{history or '(none)'}\n\n"
            f"Write the next message to the buyer."
        )
        text = self.llm.complete_text(_SYSTEM, user)
        return DraftMessage(text=text, tone=tone)
