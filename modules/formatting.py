"""Small display helpers: money and month names."""

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTH_SHORT = [name[:3] for name in MONTH_NAMES]
CURRENCY = "KES"


def format_money(value):
    """Format a number as e.g. 'KES 12,500.00'."""
    return f"{CURRENCY} {float(value or 0):,.2f}"


def period_label(month, year):
    """Return a label such as 'November 2026'."""
    return f"{MONTH_NAMES[month - 1]} {year}"
