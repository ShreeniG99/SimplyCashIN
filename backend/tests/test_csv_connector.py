import io

import pytest

from app.ingestion.csv_connector import CSVConnector
from app.domain.enums import InvoiceStatus


CSV_SAMPLE = (
    "buyer_name,buyer_tier,relationship_years,on_time_rate,preferred_channel,invoice_number,amount_rupees,due_date,status\n"
    "Anand Motors,Regular - 3 yrs,3.0,0.82,WhatsApp Business,INV-3000,150000.00,2026-04-01,overdue\n"
    "KP Auto,New - 2 mo,0.2,0.50,SMS,INV-3001,50000.00,2026-05-10,due\n"
).encode("utf-8")


def test_csv_connector_parses_two_rows():
    conn = CSVConnector()
    pairs = conn.parse(CSV_SAMPLE, "ramesh")
    assert len(pairs) == 2
    buyer, invoice = pairs[0]
    assert buyer.name == "Anand Motors"
    assert buyer.tier == "Regular - 3 yrs"
    assert invoice.number == "INV-3000"
    assert invoice.amount_paise == 150000 * 100
    assert invoice.status == InvoiceStatus.OVERDUE


def test_csv_connector_default_status():
    csv = (
        "buyer_name,buyer_tier,relationship_years,on_time_rate,preferred_channel,invoice_number,amount_rupees,due_date\n"
        "Anand,Regular,1.0,0.8,WhatsApp,INV-1,10000.00,2026-04-01\n"
    ).encode("utf-8")
    pairs = CSVConnector().parse(csv, "ramesh")
    assert pairs[0][1].status == InvoiceStatus.OVERDUE
