from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import BuyerRepo, EscalationRepo


async def resolve_escalation(session: AsyncSession, esc_id: str, action: str,
                             text: str | None, owner_id: str) -> dict:
    """Shared HITL resolution used by the REST route and the WS gateway.
    Raises LookupError (unknown/foreign escalation) or ValueError (bad action).
    On approve/edit -> dispatch + memory, exactly like an ACT-path send."""
    from app.channels.factory import get_channel

    repo = EscalationRepo(session)
    try:
        row = await repo.get(esc_id)
        buyer = await BuyerRepo(session).get(row.buyer_id)
    except Exception:
        raise LookupError("escalation not found")
    if buyer.owner_id != owner_id:
        raise LookupError("escalation not found")

    channel = get_channel()
    sent_text: str | None = None
    if action == "approve" and row.draft_text:
        channel.send(buyer_id=row.buyer_id, message=row.draft_text,
                     channel_kind=row.channel_kind or "WhatsApp Business")
        resolution = "approved"
        sent_text = row.draft_text
    elif action == "edit" and text:
        channel.send(buyer_id=row.buyer_id, message=text,
                     channel_kind=row.channel_kind or "WhatsApp Business")
        resolution = "edited"
        sent_text = text
    elif action == "override":
        resolution = "overridden"
    else:
        raise ValueError("invalid action or missing text")

    if sent_text is not None:
        # Spec: on approve -> dispatch + memory. Record the owner-approved
        # send exactly like an ACT-path send.
        from app.domain.enums import Tone
        from app.retrieval.embedder import StubEmbedder
        from app.retrieval.vector_store import PgVectorStore
        from app.services.memory import MemoryService
        memory = MemoryService(session, PgVectorStore(session, StubEmbedder(),
                                                      owner_id=owner_id))
        await memory.record_outcome(
            buyer_id=row.buyer_id,
            tone=Tone(row.draft_tone) if row.draft_tone else Tone.GENTLE,
            plan=None, timing="after owner approval", paid=False)

    await repo.resolve(esc_id, resolution)
    return {"id": esc_id, "resolved": True, "resolution": resolution}
