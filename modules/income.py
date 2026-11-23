"""Module 2: income records (create, view, edit, delete)."""
from modules import ledger
from modules.models import Income


def add_income(user_id, amount, transaction_date, category_id, description=""):
    return ledger.create(Income, user_id, amount, transaction_date, category_id, description)


def get_income(user_id, transaction_id):
    return ledger.get(user_id, transaction_id, Income)


def list_income(user_id, date_from=None, date_to=None, category_id=None, text=None):
    return ledger.search(user_id, "income", category_id, date_from, date_to, text)


def update_income(user_id, transaction_id, amount, transaction_date, category_id, description=""):
    return ledger.update(Income, user_id, transaction_id, amount, transaction_date,
                         category_id, description)


def delete_income(user_id, transaction_id):
    return ledger.delete(user_id, transaction_id, Income)
