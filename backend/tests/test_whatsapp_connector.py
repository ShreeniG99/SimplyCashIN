from app.ingestion.whatsapp_connector import WhatsAppConnector
from app.domain.enums import InvoiceStatus


def test_whatsapp_connector_extracts_amounts():
    raw = (
        "+91 98765 43210 (Anand Motors)\n"
        "Anand: Please pay Rs 25,000 for last order by 15/04/2026\n"
        "Ramesh: Sure, will process\n"
        "Anand: Also the new invoice is Rs 50,000 rupees due 20/04/2026\n"
    ).encode("utf-8")
    conn = WhatsAppConnector()
    pairs = conn.parse(raw, "ramesh")
    assert len(pairs) == 1
    buyer, invoice = pairs[0]
    assert buyer.name == "Anand Motors"
    # Rs 25,000 -> 25000 * 100 = 2,500,000 paise
    assert invoice.amount_paise == 25000 * 100
    assert invoice.status == InvoiceStatus.OVERDUE
    assert invoice.number.startswith("WA-")


def test_whatsapp_connector_no_amount():
    raw = b"+91 98765 43210 (Anand Motors)\nHello, how are you?\n"
    pairs = WhatsAppConnector().parse(raw, "ramesh")
    assert pairs == []
