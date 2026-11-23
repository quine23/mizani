"""Module 3: expense records (create, view, edit, delete)."""
from modules import ledger
from modules.models import Expense


def add_expense(user_id, amount, transaction_date, category_id, description=""):
    return ledger.create(Expense, user_id, amount, transaction_date, category_id, description)


def get_expense(user_id, transaction_id):
    return ledger.get(user_id, transaction_id, Expense)


def list_expenses(user_id, date_from=None, date_to=None, category_id=None, text=None):
    return ledger.search(user_id, "expense", category_id, date_from, date_to, text)


def update_expense(user_id, transaction_id, amount, transaction_date, category_id, description=""):
    return ledger.update(Expense, user_id, transaction_id, amount, transaction_date,
                         category_id, description)


def delete_expense(user_id, transaction_id):
    return ledger.delete(user_id, transaction_id, Expense)
