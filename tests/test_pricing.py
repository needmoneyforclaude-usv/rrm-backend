from datetime import date, datetime
from decimal import Decimal

from app.services.pricing import calculate_discount, calculate_price


def test_no_discount_under_two_years():
    assert calculate_discount(date(2025, 3, 1), date(2026, 11, 20)) == 0


def test_discount_counts_only_full_periods():
    # 3 ani si ceva -> o singura perioada de 2 ani
    assert calculate_discount(date(2023, 10, 1), date(2026, 11, 20)) == 5


def test_discount_before_anniversary():
    # 4 ani se implinesc abia pe 21.11
    assert calculate_discount(date(2022, 11, 21), date(2026, 11, 20)) == 5
    assert calculate_discount(date(2022, 11, 21), date(2026, 11, 21)) == 10


def test_discount_is_capped_at_25():
    assert calculate_discount(date(2005, 1, 1), date(2026, 11, 20)) == 25


def test_price_with_discount():
    quote = calculate_price(120, datetime(2026, 11, 20, 9, 0),
                            datetime(2026, 11, 20, 13, 0), date(2019, 3, 15))
    assert quote.price == Decimal("480.00")
    assert quote.discount == 15
    assert quote.final_price == Decimal("408.00")
