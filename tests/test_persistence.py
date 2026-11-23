from database import db_connection as db
from modules import expenses
from tests.base import FinanceTestCase


class PersistenceTests(FinanceTestCase):
    def test_records_survive_reopening_the_database(self):
        expenses.add_expense(self.alice.user_id, 250, "2026-11-01", self.expense_cat, "Saved")
        db.set_db_path(self.db_path)  # "close and reopen the application"
        db.init_db()                  # running setup again must not wipe or duplicate anything
        self.assertEqual([e.description for e in expenses.list_expenses(self.alice.user_id)], ["Saved"])
        self.assertEqual(len(db.query_all("SELECT 1 FROM categories WHERE user_id IS NULL AND category_name = 'Food'")), 1)
