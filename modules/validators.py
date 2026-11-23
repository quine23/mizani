"""Input validation shared by all modules.

Every `clean_*` function returns a cleaned value or raises ValueError with a
message that is safe to show to the user. The Validator class collects those
messages per field so a form can show all its problems at once.
"""
import calendar
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from modules.errors import ValidationError

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_AMOUNT = Decimal("1000000000")
MIN_DATE = date(2000, 1, 1)
MAX_DATE = date(2100, 12, 31)
VALID_TYPES = ("income", "expense")


class Validator:
    """Collects field errors instead of stopping at the first one."""

    def __init__(self):
        self.errors = {}

    def check(self, field, func, *args):
        try:
            return func(*args)
        except ValueError as exc:
            self.errors[field] = str(exc)
            return None

    def raise_if_invalid(self):
        if self.errors:
            raise ValidationError(self.errors)


def clean_full_name(raw):
    name = " ".join(str(raw or "").split())
    if len(name) < 2:
        raise ValueError("Enter your full name (at least 2 characters).")
    if len(name) > 80:
        raise ValueError("Name must be 80 characters or fewer.")
    return name


def clean_email(raw):
    email = str(raw or "").strip().lower()
    if not email:
        raise ValueError("Enter your email address.")
    if len(email) > 254 or not EMAIL_PATTERN.match(email):
        raise ValueError("Enter a valid email address, for example name@example.com.")
    return email


def clean_password(raw):
    password = str(raw or "")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if len(password) > 128:
        raise ValueError("Password must be 128 characters or fewer.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("Password must contain at least one letter and one number.")
    return password


def clean_amount(raw):
    """Return a positive float with at most two decimal places."""
    text = str(raw if raw is not None else "").strip().replace(",", "")
    if not text:
        raise ValueError("Enter an amount.")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError("Amount must be a number, for example 1500 or 1500.50.") from None
    if not value.is_finite():
        raise ValueError("Amount must be a number, for example 1500 or 1500.50.")
    if value <= 0:
        raise ValueError("Amount must be greater than zero.")
    if value > MAX_AMOUNT:
        raise ValueError("Amount is too large.")
    rounded = value.quantize(Decimal("0.01"))
    if value != rounded:
        raise ValueError("Amount can have at most 2 decimal places.")
    return float(rounded)


def clean_date(raw):
    """Return the date as an ISO string (YYYY-MM-DD)."""
    text = str(raw or "").strip()
    if not text:
        raise ValueError("Choose a date.")
    if not DATE_PATTERN.match(text):
        raise ValueError("Enter a valid date in YYYY-MM-DD format.")
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        raise ValueError("That date does not exist. Check the day and month.") from None
    if not MIN_DATE <= parsed <= MAX_DATE:
        raise ValueError("Date must be between 2000 and 2100.")
    return parsed.isoformat()


def clean_description(raw, max_len=200):
    text = " ".join(str(raw or "").split())
    if len(text) > max_len:
        raise ValueError(f"Description must be {max_len} characters or fewer.")
    return text


def clean_category_name(raw):
    name = " ".join(str(raw or "").split())
    if len(name) < 2:
        raise ValueError("Category name must be at least 2 characters.")
    if len(name) > 40:
        raise ValueError("Category name must be 40 characters or fewer.")
    return name


def clean_int(raw, message, low, high):
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        raise ValueError(message) from None
    if not low <= value <= high:
        raise ValueError(message)
    return value


def clean_type(raw):
    value = str(raw or "").strip().lower()
    if value not in VALID_TYPES:
        raise ValueError("Type must be income or expense.")
    return value


def month_bounds(month, year):
    """First and last day of a month as ISO strings."""
    last_day = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"


def year_bounds(year):
    return f"{year:04d}-01-01", f"{year:04d}-12-31"
