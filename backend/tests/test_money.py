from app.money import format_inr


def test_format_inr_lakhs():
    assert format_inr(240000_00) == "₹2,40,000"   # 2.4 lakh rupees in paise


def test_format_inr_thousands():
    assert format_inr(85000_00) == "₹85,000"


def test_format_inr_small():
    assert format_inr(500_00) == "₹500"


def test_format_inr_zero():
    assert format_inr(0) == "₹0"
