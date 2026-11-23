"""Module 5: monthly budgets and warnings.

A budget is either for one expense category or, when category_id is None, an
overall limit for the month. Spending is always calculated from the saved
expense transactions, never stored.
"""
from database import db_connection as db
from modules import categories
from modules.errors import NotFoundError
from modules.models import Budget
from modules.validators import Validator, clean_amount, clean_int, month_bounds

_SPENT_SQL = (
    "COALESCE((SELECT SUM(t.amount) FROM transactions t "
    "WHERE t.user_id = b.user_id AND t.transaction_type = 'expense' "
    "AND t.transaction_date BETWEEN ? AND ? "
    "AND (b.category_id IS NULL OR t.category_id = b.category_id)), 0)"
)


def _from_row(row):
    return Budget(
        budget_id=row["budget_id"], user_id=row["user_id"], category_id=row["category_id"],
        category_name=row["category_name"], amount=row["budget_amount"],
        month=row["month"], year=row["year"], spent=round(row["spent"], 2),
    )


def set_budget(user_id, amount, month, year, category_id=None):
    """Create a budget, or replace the limit if one already exists for that month."""
    v = Validator()
    amount = v.check("amount", clean_amount, amount)
    month = v.check("month", clean_int, month, "Choose a month.", 1, 12)
    year = v.check("year", clean_int, year, "Enter a year between 2000 and 2100.", 2000, 2100)
    if category_id not in (None, "", "all"):
        category_id = v.check("category_id", clean_int, category_id, "Choose a category.", 1, 2 ** 62)
        if category_id is not None:
            try:
                category = categories.get_category(user_id, category_id)
            except NotFoundError:
                v.errors["category_id"] = "Choose a category from the list."
            else:
                if category.category_type != "expense":
                    v.errors["category_id"] = "Budgets can only be set for expense categories."
    else:
        category_id = None
    v.raise_if_invalid()

    existing = db.query_one(
        "SELECT budget_id FROM budgets WHERE user_id = ? AND month = ? AND year = ? "
        "AND ((category_id IS NULL AND ? IS NULL) OR category_id = ?)",
        (user_id, month, year, category_id, category_id),
    )
    if existing:
        db.execute("UPDATE budgets SET budget_amount = ? WHERE budget_id = ? AND user_id = ?",
                   (amount, existing["budget_id"], user_id))
        budget_id = existing["budget_id"]
    else:
        budget_id = db.execute(
            "INSERT INTO budgets (user_id, category_id, budget_amount, month, year) "
            "VALUES (?, ?, ?, ?, ?)", (user_id, category_id, amount, month, year)).lastrowid
    return get_budget(user_id, budget_id)


def get_budget(user_id, budget_id):
    row = db.query_one("SELECT month, year FROM budgets WHERE budget_id = ? AND user_id = ?",
                       (budget_id, user_id))
    if row is None:
        raise NotFoundError("Budget not found.")
    first, last = month_bounds(row["month"], row["year"])
    sql = (
        f"SELECT b.*, c.category_name, {_SPENT_SQL} AS spent "
        "FROM budgets b LEFT JOIN categories c ON c.category_id = b.category_id "
        "WHERE b.user_id = ? AND b.budget_id = ?"
    )
    return _from_row(db.query_one(sql, (first, last, user_id, budget_id)))


def list_budgets(user_id, month, year):
    """All budgets for a month with spending already worked out."""
    first, last = month_bounds(month, year)
    sql = (
        f"SELECT b.*, c.category_name, {_SPENT_SQL} AS spent "
        "FROM budgets b LEFT JOIN categories c ON c.category_id = b.category_id "
        "WHERE b.user_id = ? AND b.month = ? AND b.year = ? "
        "ORDER BY b.category_id IS NOT NULL, c.category_name COLLATE NOCASE"
    )
    return [_from_row(r) for r in db.query_all(sql, (first, last, user_id, month, year))]


def budget_alerts(user_id, month, year):
    """Budgets that are at or past the warning threshold, worst first."""
    flagged = [b for b in list_budgets(user_id, month, year) if b.status != "ok"]
    return sorted(flagged, key=lambda b: b.percent_used, reverse=True)


def delete_budget(user_id, budget_id):
    budget = get_budget(user_id, budget_id)
    db.execute("DELETE FROM budgets WHERE budget_id = ? AND user_id = ?", (budget_id, user_id))
    return budget
