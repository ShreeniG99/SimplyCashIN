import datetime as dt

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import Orchestrator
from app.api import schemas
from app.api.deps import OWNER_ID, get_orchestrator
from app.db.repositories import (
    BuyerRepo, CashEventRepo, ConversationRepo, EscalationRepo, InvoiceRepo, OwnerRepo,
)
from app.db.session import get_session
from app.domain.enums import CashEventStatus, Direction, InvoiceStatus
from app.money import format_inr

router = APIRouter()
TODAY = dt.date(2026, 5, 18)


@router.get("/buyers", response_model=list[schemas.BuyerOut])
async def list_buyers(session: AsyncSession = Depends(get_session)):
    buyers = await BuyerRepo(session).list_for_owner(OWNER_ID)
    out = []
    for b in buyers:
        inv = await InvoiceRepo(session).latest_for_buyer(b.id)
        action = {"overdue": "Needs follow-up", "due": "Reminder scheduled",
                  "paid": "Paid in full"}[inv.status.value]
        out.append(schemas.BuyerOut(
            id=b.id, name=b.name, tier=b.tier, amount=format_inr(inv.amount_paise),
            overdue=inv.days_overdue, status=inv.status.value,
            agent=None, action=action, escalated=False))
    return out


@router.get("/buyers/{buyer_id}", response_model=schemas.BuyerDetailOut)
async def buyer_detail(buyer_id: str, session: AsyncSession = Depends(get_session)):
    from app.retrieval.embedder import StubEmbedder
    from app.retrieval.vector_store import PgVectorStore
    try:
        buyer = await BuyerRepo(session).get(buyer_id)
    except Exception:
        raise HTTPException(status_code=404, detail="buyer not found")
    invoice = await InvoiceRepo(session).latest_for_buyer(buyer_id)
    thread = await ConversationRepo(session).thread_for_buyer(buyer_id)
    snippets = await PgVectorStore(session, StubEmbedder()).search(
        buyer_id, "what worked best", k=1)
    return schemas.BuyerDetailOut(
        id=buyer.id, name=buyer.name, tier=buyer.tier,
        preferred_channel=buyer.preferred_channel, on_time_rate=buyer.on_time_rate,
        invoice=schemas.InvoiceOut(
            number=invoice.number, amount=format_inr(invoice.amount_paise),
            amount_paise=invoice.amount_paise, overdue=invoice.days_overdue,
            status=invoice.status.value),
        thread=[schemas.ThreadTurnOut(sender=t.sender, agent=t.agent, text=t.text,
                                      created_at=t.created_at.isoformat())
                for t in thread],
        best_approach=snippets[0] if snippets else None,
    )


@router.post("/buyers/{buyer_id}/run-cycle", response_model=schemas.CycleOut)
async def run_cycle(buyer_id: str, session: AsyncSession = Depends(get_session),
                    orchestrator: Orchestrator = Depends(get_orchestrator)):
    try:
        buyer = await BuyerRepo(session).get(buyer_id)
    except Exception:
        raise HTTPException(status_code=404, detail="buyer not found")
    owner = await OwnerRepo(session).get(OWNER_ID)
    invoice = await InvoiceRepo(session).latest_for_buyer(buyer_id)
    thread = await ConversationRepo(session).thread_for_buyer(buyer_id)

    result = await orchestrator.run_cycle(owner, buyer, invoice, thread)
    await session.commit()

    if result.escalation:
        await EscalationRepo(session).save(
            result.escalation,
            draft_text=result.draft.text if result.draft else None,
            channel_kind=buyer.preferred_channel)
        await session.commit()

    plan_out = []
    if result.plan:
        for i in result.plan.installments:
            due = "Today" if i.due_offset_days == 0 else f"In {i.due_offset_days} days"
            plan_out.append(schemas.InstallmentOut(
                n=i.seq, label=i.label, amount=format_inr(i.amount_paise), due=due))
    return schemas.CycleOut(
        decision=result.decision.value,
        draft=result.draft.text if result.draft else None,
        tone=result.draft.tone.value if result.draft else None,
        plan=plan_out,
        checks=[schemas.CheckOut(label=c.label, value=c.value, ok=c.ok) for c in result.checks],
        escalation_reason=result.escalation.reason if result.escalation else None,
        recommendation=result.escalation.recommendation if result.escalation else None,
        escalation_id=result.escalation.id if result.escalation else None,
        urgency=result.urgency.score,
        breaching_need=result.urgency.breaching_need,
    )


@router.get("/cash-calendar", response_model=schemas.CashCalendarOut)
async def cash_calendar(session: AsyncSession = Depends(get_session)):
    events = await CashEventRepo(session).for_owner(OWNER_ID)
    by_day: dict[dt.date, list] = {}
    for e in events:
        by_day.setdefault(e.due_date, []).append(e)
    days = []
    for day in sorted(by_day):
        evs = by_day[day]
        days.append(schemas.CashDayOut(
            date=day.isoformat(),
            in_dots=sum(1 for e in evs if e.direction == Direction.IN),
            out_dots=sum(1 for e in evs if e.direction == Direction.OUT)))
    week_end = TODAY + dt.timedelta(days=7)
    week = [schemas.CashItemOut(
        id=e.id, date=e.due_date.isoformat(), direction=e.direction.value,
        label=e.label, counterparty=e.counterparty, amount=format_inr(e.amount_paise),
        done=e.status == CashEventStatus.DONE)
        for e in events if TODAY <= e.due_date <= week_end]
    return schemas.CashCalendarOut(days=days, week=week)


@router.post("/cash-events/{event_id}/toggle", response_model=schemas.CashItemOut)
async def toggle_cash_event(event_id: str, session: AsyncSession = Depends(get_session)):
    try:
        e = await CashEventRepo(session).toggle(event_id)
    except Exception:
        raise HTTPException(status_code=404, detail="cash event not found")
    return schemas.CashItemOut(
        id=e.id, date=e.due_date.isoformat(), direction=e.direction.value,
        label=e.label, counterparty=e.counterparty, amount=format_inr(e.amount_paise),
        done=e.status == CashEventStatus.DONE)


@router.post("/escalations/{esc_id}/resolve")
async def resolve_escalation(esc_id: str, body: schemas.ResolveIn,
                             session: AsyncSession = Depends(get_session)):
    from app.channels.simulated import SimulatedChannel
    repo = EscalationRepo(session)
    try:
        row = await repo.get(esc_id)
    except Exception:
        raise HTTPException(status_code=404, detail="escalation not found")

    channel = SimulatedChannel()
    if body.action == "approve" and row.draft_text:
        channel.send(buyer_id=row.buyer_id, message=row.draft_text,
                     channel_kind=row.channel_kind or "WhatsApp Business")
        resolution = "approved"
    elif body.action == "edit" and body.text:
        channel.send(buyer_id=row.buyer_id, message=body.text,
                     channel_kind=row.channel_kind or "WhatsApp Business")
        resolution = "edited"
    elif body.action == "override":
        resolution = "overridden"
    else:
        raise HTTPException(status_code=400, detail="invalid action or missing text")

    await repo.resolve(esc_id, resolution)
    return {"id": esc_id, "resolved": True, "resolution": resolution}


# ---- M2: Ingestion ----

@router.post("/ingest/csv")
async def ingest_csv(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    from app.ingestion.csv_connector import CSVConnector
    from app.services.ingestion import IngestionService
    from app.domain.enums import IngestionSource

    raw = await file.read()
    svc = IngestionService(session)
    try:
        job_id = await svc.ingest(raw, OWNER_ID, CSVConnector(), IngestionSource.CSV)
        return {"job_id": job_id, "status": "submitted"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/ingest/whatsapp")
async def ingest_whatsapp(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    from app.ingestion.whatsapp_connector import WhatsAppConnector
    from app.services.ingestion import IngestionService
    from app.domain.enums import IngestionSource

    raw = await file.read()
    svc = IngestionService(session)
    try:
        job_id = await svc.ingest(raw, OWNER_ID, WhatsAppConnector(), IngestionSource.WHATSAPP)
        return {"job_id": job_id, "status": "submitted"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/ingest/jobs", response_model=list[schemas.IngestionJobOut])
async def list_ingestion_jobs(session: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    from app.db.models import IngestionJobRow
    rows = await session.execute(
        select(IngestionJobRow).where(IngestionJobRow.owner_id == OWNER_ID)
    )
    return [schemas.IngestionJobOut(
        id=r.id, source=r.source, status=r.status,
        total_rows=r.total_rows, imported_rows=r.imported_rows,
        error_message=r.error_message,
        created_at=r.created_at.isoformat() if r.created_at else None,
        completed_at=r.completed_at.isoformat() if r.completed_at else None,
    ) for r in rows.scalars().all()]


# ---- M2: Redis Queue ----

@router.get("/queue", response_model=schemas.QueueStatusOut)
async def get_queue():
    from app.queue.redis_queue import RedisUrgencyQueue
    try:
        q = RedisUrgencyQueue()
        items = q.peek(k=5, owner_id=OWNER_ID)
        return schemas.QueueStatusOut(
            size=q.size(owner_id=OWNER_ID),
            items=[schemas.QueuedItemOut(
                buyer_id=i["buyer_id"], invoice_id=i["invoice_id"],
                urgency_score=i["urgency_score"], due_date=i["due_date"]) for i in items])
    except Exception:
        return schemas.QueueStatusOut(size=0, items=[])


@router.post("/queue/pop")
async def pop_queue():
    from app.queue.redis_queue import RedisUrgencyQueue
    q = RedisUrgencyQueue()
    item = q.pop(owner_id=OWNER_ID)
    if not item:
        raise HTTPException(status_code=404, detail="queue empty")
    return item


# ---- M2: Scheduler ----

@router.get("/schedule/status")
async def schedule_status():
    from app.queue.redis_queue import RedisUrgencyQueue
    try:
        q = RedisUrgencyQueue()
        return {"status": "ready", "queue_size": q.size(owner_id=OWNER_ID)}
    except Exception:
        return {"status": "redis_unavailable", "queue_size": 0}


@router.post("/schedule/trigger")
async def trigger_schedule():
    from app.scheduler.daily import DailyOverdueTrigger
    from app.db.session import SessionFactory
    trigger = DailyOverdueTrigger(SessionFactory)
    result = await trigger.run(owner_id=OWNER_ID)
    return result
