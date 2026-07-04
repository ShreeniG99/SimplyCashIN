import pytest
from sqlalchemy import func, select

from app.db.models import BuyerRow, InvoiceRow, MemoryEmbeddingRow, OwnerRow
from app.domain.enums import IngestionSource, JobStatus
from app.ingestion.csv_connector import CSVConnector
from app.services.ingestion import IngestionService

CSV_SAMPLE = (
    "buyer_name,buyer_tier,relationship_years,on_time_rate,preferred_channel,"
    "invoice_number,amount_rupees,due_date,status\n"
    "Anand Motors,Regular - 3 yrs,3.0,0.82,WhatsApp Business,INV-3000,150000.00,2026-04-01,overdue\n"
    "KP Auto,New - 2 mo,0.2,0.50,SMS,INV-3001,50000.00,2026-05-10,due\n"
).encode("utf-8")


async def _seed_owner(session):
    session.add(OwnerRow(id="ramesh", name="R", business="B",
                         max_extension_days=30, min_upfront_pct=30))
    await session.commit()


@pytest.mark.db
async def test_ingest_csv_lands_invoices_and_embeddings(session):
    await _seed_owner(session)
    svc = IngestionService(session)
    job_id = await svc.ingest(CSV_SAMPLE, "ramesh", CSVConnector(), IngestionSource.CSV)
    assert job_id

    n_inv = (await session.execute(
        select(func.count()).select_from(InvoiceRow))).scalar_one()
    assert n_inv == 2
    # M2 vectorization pipeline: each ingested invoice is embedded into pgvector
    n_emb = (await session.execute(
        select(func.count()).select_from(MemoryEmbeddingRow))).scalar_one()
    assert n_emb == 2


@pytest.mark.db
async def test_reingest_links_invoice_to_existing_buyer(session):
    await _seed_owner(session)
    svc = IngestionService(session)
    await svc.ingest(CSV_SAMPLE, "ramesh", CSVConnector(), IngestionSource.CSV)
    await svc.ingest(CSV_SAMPLE, "ramesh", CSVConnector(), IngestionSource.CSV)

    n_buyers = (await session.execute(
        select(func.count()).select_from(BuyerRow))).scalar_one()
    assert n_buyers == 2          # no duplicate buyers
    n_inv = (await session.execute(
        select(func.count()).select_from(InvoiceRow))).scalar_one()
    assert n_inv == 4             # invoices attach to the existing buyer rows


@pytest.mark.db
async def test_failed_ingest_marks_job_failed(session):
    await _seed_owner(session)

    class ExplodingConnector:
        def parse(self, raw, owner_id):
            raise ValueError("boom")

    svc = IngestionService(session)
    with pytest.raises(ValueError):
        await svc.ingest(b"x", "ramesh", ExplodingConnector(), IngestionSource.CSV)

    from app.db.models import IngestionJobRow
    row = (await session.execute(select(IngestionJobRow))).scalar_one()
    assert row.status == JobStatus.FAILED.value
    assert "boom" in (row.error_message or "")
