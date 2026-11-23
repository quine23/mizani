"""Module 7: balances, monthly summaries and automatic financial insights."""
from database import db_connection as db
from modules import budgets
from modules.formatting import MONTH_NAMES, MONTH_SHORT, format_money, period_label
from modules.validators import month_bounds, year_bounds


def previous_period(month, year):
    return (12, year - 1) if month == 1 else (month - 1, year)


def totals(user_id, date_from=None, date_to=None):
    """Total income, total expenses and balance (income minus expenses)."""
    sql = ("SELECT transaction_type, COALESCE(SUM(amount), 0) AS total "
           "FROM transactions WHERE user_id = ?")
    params = [user_id]
    if date_from:
        sql += " AND transaction_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND transaction_date <= ?"
        params.append(date_to)
    sql += " GROUP BY transaction_type"
    sums = {row["transaction_type"]: row["total"] for row in db.query_all(sql, params)}
    income = round(sums.get("income", 0), 2)
    expenses = round(sums.get("expense", 0), 2)
    return {"income": income, "expenses": expenses, "balance": round(income - expenses, 2)}


def category_breakdown(user_id, txn_type, month, year):
    """Spending (or income) per category for a month, largest first, with % share."""
    first, last = month_bounds(month, year)
    rows = db.query_all(
        "SELECT c.category_name AS name, SUM(t.amount) AS total, COUNT(*) AS count "
        "FROM transactions t JOIN categories c ON c.category_id = t.category_id "
        "WHERE t.user_id = ? AND t.transaction_type = ? AND t.transaction_date BETWEEN ? AND ? "
        "GROUP BY c.category_id ORDER BY total DESC, name",
        (user_id, txn_type, first, last))
    grand_total = sum(r["total"] for r in rows)
    return [{
        "name": r["name"], "total": round(r["total"], 2), "count": r["count"],
        "share": round(r["total"] / grand_total * 100, 1) if grand_total else 0.0,
    } for r in rows]


def monthly_series(user_id, year):
    """Income and expenses for each of the 12 months of a year."""
    first, last = year_bounds(year)
    rows = db.query_all(
        "SELECT CAST(substr(transaction_date, 6, 2) AS INTEGER) AS month, transaction_type, "
        "SUM(amount) AS total FROM transactions "
        "WHERE user_id = ? AND transaction_date BETWEEN ? AND ? "
        "GROUP BY month, transaction_type", (user_id, first, last))
    series = [{"month": m, "label": MONTH_SHORT[m - 1], "income": 0.0, "expenses": 0.0}
              for m in range(1, 13)]
    for row in rows:
        key = "income" if row["transaction_type"] == "income" else "expenses"
        series[row["month"] - 1][key] = round(row["total"], 2)
    for entry in series:
        entry["net"] = round(entry["income"] - entry["expenses"], 2)
    return series


def monthly_summary(user_id, month, year):
    first, last = month_bounds(month, year)
    month_totals = totals(user_id, first, last)
    count = db.query_one(
        "SELECT COUNT(*) AS n FROM transactions WHERE user_id = ? AND transaction_date BETWEEN ? AND ?",
        (user_id, first, last))["n"]
    spending = category_breakdown(user_id, "expense", month, year)
    earnings = category_breakdown(user_id, "income", month, year)
    income_total = month_totals["income"]
    net = round(income_total - month_totals["expenses"], 2)
    return {
        "month": month, "year": year, "label": period_label(month, year),
        "income": income_total, "expenses": month_totals["expenses"], "net": net,
        "savings_rate": round(net / income_total * 100, 1) if income_total else None,
        "transaction_count": count,
        "expense_categories": spending, "income_categories": earnings,
        "top_expense_category": spending[0] if spending else None,
    }


def insights(user_id, month, year):
    """Plain-language sentences that summarise the month automatically."""
    summary = monthly_summary(user_id, month, year)
    label = summary["label"]
    if summary["transaction_count"] == 0:
        return [f"No transactions are recorded for {label} yet."]

    messages = []
    if summary["net"] >= 0:
        if summary["savings_rate"] is not None:
            messages.append(f"In {label} you kept {format_money(summary['net'])}, "
                            f"which is {summary['savings_rate']}% of your income.")
        else:
            messages.append(f"In {label} you recorded no income and no net spending.")
    else:
        messages.append(f"In {label} you spent {format_money(-summary['net'])} more than you earned.")

    top = summary["top_expense_category"]
    if top:
        messages.append(f"Your biggest expense category was {top['name']} at "
                        f"{format_money(top['total'])} ({top['share']}% of spending).")

    prev_month, prev_year = previous_period(month, year)
    prev_expenses = totals(user_id, *month_bounds(prev_month, prev_year))["expenses"]
    if prev_expenses > 0:
        change = round((summary["expenses"] - prev_expenses) / prev_expenses * 100, 1)
        word = "higher" if change > 0 else "lower"
        if change == 0:
            messages.append(f"Spending is the same as {MONTH_NAMES[prev_month - 1]}.")
        else:
            messages.append(f"Spending is {abs(change)}% {word} than {MONTH_NAMES[prev_month - 1]} "
                            f"({format_money(prev_expenses)}).")

    for budget in budgets.budget_alerts(user_id, month, year):
        if budget.status == "exceeded":
            messages.append(f"{budget.label} is over budget by {format_money(budget.overspent_by)}.")
        else:
            messages.append(f"{budget.label} has used {budget.percent_used}% of its budget; "
                            f"{format_money(budget.remaining)} is left.")
    return messages


def dashboard(user_id, month, year):
    """Everything the dashboard page needs in one call."""
    return {
        "balance": totals(user_id),
        "summary": monthly_summary(user_id, month, year),
        "budgets": budgets.list_budgets(user_id, month, year),
        "insights": insights(user_id, month, year),
    }
