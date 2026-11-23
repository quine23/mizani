"""Module 6: combined transaction history, search, filtering and sorting.

Searching and filtering are done by the database; sorting is done here in
Python with sorted() and a key function chosen by the user.
"""
import re

from modules import expenses, income, ledger
from modules.models import Expense, Income
from modules.validators import (Validator, clean_date, clean_int, clean_type,
                                month_bounds)

SORT_KEYS = {
    "date": lambda t: (t.transaction_date, t.transaction_id or 0),
    "amount": lambda t: t.amount,
    "category": lambda t: (t.category_name or "").lower(),
    "type": lambda t: t.transaction_type,
}
_MONTH_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")


def _clean_month(raw):
    match = _MONTH_PATTERN.match(str(raw).strip())
    if not match or not (1 <= int(match.group(2)) <= 12) or not (2000 <= int(match.group(1)) <= 2100):
        raise ValueError("Choose a month like 2026-11.")
    return month_bounds(int(match.group(2)), int(match.group(1)))


def parse_filters(args):
    """Turn query-string values (a dict-like object) into search_transactions() arguments."""
    v = Validator()
    filters = {}

    kind = (args.get("type") or "").strip()
    if kind:
        filters["txn_type"] = v.check("type", clean_type, kind)

    category = (args.get("category") or "").strip()
    if category:
        filters["category_id"] = v.check("category", clean_int, category,
                                         "Choose a category from the list.", 1, 2 ** 62)

    month = (args.get("month") or "").strip()
    if month:
        bounds = v.check("month", _clean_month, month)
        if bounds:
            filters["date_from"], filters["date_to"] = bounds
    else:
        date_from = (args.get("from") or "").strip()
        date_to = (args.get("to") or "").strip()
        if date_from:
            filters["date_from"] = v.check("from", clean_date, date_from)
        if date_to:
            filters["date_to"] = v.check("to", clean_date, date_to)
        if filters.get("date_from") and filters.get("date_to") and filters["date_from"] > filters["date_to"]:
            v.errors["to"] = "The end date must be on or after the start date."

    text = " ".join((args.get("q") or "").split())[:100]
    if text:
        filters["text"] = text

    sort = args.get("sort") or "date"
    filters["sort"] = sort if sort in SORT_KEYS else "date"
    filters["direction"] = "asc" if args.get("dir") == "asc" else "desc"

    v.raise_if_invalid()
    return filters


def search_transactions(user_id, txn_type=None, category_id=None, date_from=None,
                        date_to=None, text=None, sort="date", direction="desc"):
    found = ledger.search(user_id, txn_type, category_id, date_from, date_to, text)
    key = SORT_KEYS.get(sort, SORT_KEYS["date"])
    return sorted(found, key=key, reverse=(direction != "asc"))


def get_transaction(user_id, transaction_id):
    return ledger.get(user_id, transaction_id)


def update_transaction(user_id, transaction_id, amount, transaction_date, category_id, description=""):
    """Send the edit to the income or expense operation that matches the record."""
    txn = ledger.get(user_id, transaction_id)
    handlers = {Income: income.update_income, Expense: expenses.update_expense}
    return handlers[type(txn)](user_id, transaction_id, amount, transaction_date,
                               category_id, description)


def delete_transaction(user_id, transaction_id):
    txn = ledger.get(user_id, transaction_id)
    handlers = {Income: income.delete_income, Expense: expenses.delete_expense}
    return handlers[type(txn)](user_id, transaction_id)


def summarize(transactions):
    """Totals for a list of transactions, using each object's signed_amount()."""
    income_total = sum(t.amount for t in transactions if t.transaction_type == "income")
    expense_total = sum(t.amount for t in transactions if t.transaction_type == "expense")
    return {
        "count": len(transactions),
        "income": round(income_total, 2),
        "expenses": round(expense_total, 2),
        "net": round(sum(t.signed_amount() for t in transactions), 2),
    }
