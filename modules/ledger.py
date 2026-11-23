"""Shared data access for the transactions table.

income.py and expenses.py are thin wrappers over this module, and
transactions.py builds the combined history on top of it. Every query is
filtered by user_id, so a user can never read or change someone else's data.
"""
from database import db_connection as db
from modules import categories
from modules.errors import NotFoundError
from modules.models import Expense, Income, transaction_from_row
from modules.validators import (Validator, clean_amount, clean_date,
                                clean_description, clean_int)

_SELECT = (
    "SELECT t.transaction_id, t.user_id, t.category_id, t.transaction_type, t.amount, "
    "t.description, t.transaction_date, t.created_at, c.category_name "
    "FROM transactions t JOIN categories c ON c.category_id = t.category_id"
)


def _clean_fields(txn_class, user_id, amount, transaction_date, category_id, description):
    v = Validator()
    amount = v.check("amount", clean_amount, amount)
    transaction_date = v.check("transaction_date", clean_date, transaction_date)
    description = v.check("description", clean_description, description)
    category_id = v.check("category_id", clean_int, category_id, "Choose a category.", 1, 2 ** 62)
    if category_id is not None:
        try:
            category = categories.get_category(user_id, category_id)
        except NotFoundError:
            v.errors["category_id"] = "Choose a category from the list."
        else:
            if category.category_type != txn_class.transaction_type:
                v.errors["category_id"] = (
                    f"'{category.name}' is an {category.category_type} category and "
                    f"cannot be used for {txn_class.transaction_type}.")
    v.raise_if_invalid()
    return amount, transaction_date, category_id, description


def create(txn_class, user_id, amount, transaction_date, category_id, description=""):
    amount, transaction_date, category_id, description = _clean_fields(
        txn_class, user_id, amount, transaction_date, category_id, description)
    txn = txn_class(user_id=user_id, category_id=category_id, amount=amount,
                    transaction_date=transaction_date, description=description)
    txn.validate()
    result = db.execute(
        "INSERT INTO transactions (user_id, category_id, transaction_type, amount, "
        "description, transaction_date) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, category_id, txn.transaction_type, amount, description, transaction_date),
    )
    return get(user_id, result.lastrowid)


def get(user_id, transaction_id, txn_class=None):
    try:
        transaction_id = int(transaction_id)
    except (TypeError, ValueError):
        raise NotFoundError("Transaction not found.") from None
    row = db.query_one(_SELECT + " WHERE t.transaction_id = ? AND t.user_id = ?",
                       (transaction_id, user_id))
    if row is None or (txn_class and row["transaction_type"] != txn_class.transaction_type):
        raise NotFoundError("Transaction not found.")
    return transaction_from_row(row)


def update(txn_class, user_id, transaction_id, amount, transaction_date, category_id, description=""):
    existing = get(user_id, transaction_id, txn_class)
    amount, transaction_date, category_id, description = _clean_fields(
        txn_class, user_id, amount, transaction_date, category_id, description)
    db.execute(
        "UPDATE transactions SET category_id = ?, amount = ?, description = ?, "
        "transaction_date = ? WHERE transaction_id = ? AND user_id = ?",
        (category_id, amount, description, transaction_date, existing.transaction_id, user_id),
    )
    return get(user_id, existing.transaction_id)


def delete(user_id, transaction_id, txn_class=None):
    existing = get(user_id, transaction_id, txn_class)
    db.execute("DELETE FROM transactions WHERE transaction_id = ? AND user_id = ?",
               (existing.transaction_id, user_id))
    return existing


def _like_pattern(text):
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def search(user_id, txn_type=None, category_id=None, date_from=None, date_to=None, text=None):
    """Return matching transactions, newest first. All filters are optional."""
    sql = _SELECT + " WHERE t.user_id = ?"
    params = [user_id]
    if txn_type:
        sql += " AND t.transaction_type = ?"
        params.append(txn_type)
    if category_id:
        sql += " AND t.category_id = ?"
        params.append(category_id)
    if date_from:
        sql += " AND t.transaction_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND t.transaction_date <= ?"
        params.append(date_to)
    if text:
        sql += (" AND (t.description LIKE ? ESCAPE '\\' "
                "OR c.category_name LIKE ? ESCAPE '\\')")
        pattern = _like_pattern(text)
        params.extend([pattern, pattern])
    sql += " ORDER BY t.transaction_date DESC, t.transaction_id DESC"
    return [transaction_from_row(row) for row in db.query_all(sql, params)]
