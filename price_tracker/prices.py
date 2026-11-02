"""Reading prices from text and writing them for people."""

import re
from decimal import Decimal, InvalidOperation


def parse_price(text: str | None) -> Decimal | None:
    """Turn text like '₹1,29,999.00' into Decimal('129999.00')."""
    if not text:
        return None
    match = re.search(r"\d[\d,]*(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return None


def format_rupees(amount: Decimal) -> str:
    """Write an amount the Indian way: 129999.5 -> '₹1,29,999.50'."""
    whole, _, paise = f"{amount:.2f}".partition(".")
    head, groups = whole[:-3], [whole[-3:]]
    while head:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return "₹" + ",".join(groups) + ("" if paise == "00" else f".{paise}")
