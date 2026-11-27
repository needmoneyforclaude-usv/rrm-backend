from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal


@dataclass
class PriceQuote:
    price: Decimal
    discount: Decimal
    final_price: Decimal


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


DISCOUNT_PER_PERIOD = 5
YEARS_PER_PERIOD = 2
MAX_DISCOUNT = 25


def full_years(start: date, end: date) -> int:
    years = end.year - start.year
    if (end.month, end.day) < (start.month, start.day):
        years -= 1
    return max(years, 0)


def calculate_discount(affiliation_date: date, on_date: date) -> Decimal:
    periods = full_years(affiliation_date, on_date) // YEARS_PER_PERIOD
    return Decimal(min(periods * DISCOUNT_PER_PERIOD, MAX_DISCOUNT))


def calculate_price(price_per_hour, start_time: datetime, end_time: datetime,
                    affiliation_date: date) -> PriceQuote:
    hours = Decimal((end_time - start_time).total_seconds()) / Decimal(3600)
    price = _money(Decimal(str(price_per_hour)) * hours)
    discount = calculate_discount(affiliation_date, start_time.date())
    final_price = _money(price * (Decimal(100) - discount) / Decimal(100))
    return PriceQuote(price=price, discount=discount, final_price=final_price)
