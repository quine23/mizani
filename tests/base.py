"""Shared test setup: every test gets its own empty database file."""
import os
import shutil
import tempfile
import unittest

from database import db_connection as db
from modules import authentication, categories

# Fewer hashing rounds keep the test suite fast; real accounts use the full default.
authentication.HASH_METHOD = "pbkdf2:sha256:1000"


class FinanceTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        db.set_db_path(self.db_path)
        db.init_db()
        self.alice = self.make_user("Alice Wanjiru", "alice@example.com")
        self.bob = self.make_user("Bob Otieno", "bob@example.com")
        self.income_cat = self.cat("Salary", "income")
        self.expense_cat = self.cat("Food", "expense")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_user(self, name, email, password="Passw0rd1"):
        return authentication.register_user(name, email, password, password)

    def cat(self, name, kind, user=None):
        """Find a default category by name (or one of the user's own)."""
        uid = (user or self.alice).user_id
        for c in categories.list_categories(uid, kind):
            if c.name == name:
                return c.category_id
        raise AssertionError(f"No {kind} category named {name}")
