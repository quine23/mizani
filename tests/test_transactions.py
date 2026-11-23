from modules import categories, expenses, income, transactions
from modules.errors import NotFoundError, ValidationError
from modules.models import Expense, Income
from tests.base import FinanceTestCase


class IncomeExpenseTests(FinanceTestCase):
    def test_income_create_view_edit_delete(self):
        uid = self.alice.user_id
        rec = income.add_income(uid, "50,000", "2026-11-01", self.income_cat, "Internship pay")
        self.assertIsInstance(rec, Income)
        self.assertEqual(rec.amount, 50000.0)
        self.assertEqual(income.get_income(uid, rec.transaction_id).description, "Internship pay")
        updated = income.update_income(uid, rec.transaction_id, 52000, "2026-11-02", self.income_cat, "Raise")
        self.assertEqual((updated.amount, updated.transaction_date), (52000.0, "2026-11-02"))
        income.delete_income(uid, rec.transaction_id)
        with self.assertRaises(NotFoundError):
            income.get_income(uid, rec.transaction_id)

    def test_expense_create_view_edit_delete(self):
        uid = self.alice.user_id
        rec = expenses.add_expense(uid, 350.5, "2026-11-03", self.expense_cat, "Lunch")
        self.assertIsInstance(rec, Expense)
        self.assertEqual(len(expenses.list_expenses(uid)), 1)
        expenses.update_expense(uid, rec.transaction_id, 400, "2026-11-03", self.expense_cat, "Lunch + juice")
        self.assertEqual(expenses.get_expense(uid, rec.transaction_id).amount, 400.0)
        expenses.delete_expense(uid, rec.transaction_id)
        self.assertEqual(expenses.list_expenses(uid), [])

    def test_bad_amounts_rejected(self):
        for bad in ["", "abc", "0", "-5", "10.555", "nan", "inf", "1e400", None]:
            with self.subTest(amount=bad):
                with self.assertRaises(ValidationError) as ctx:
                    expenses.add_expense(self.alice.user_id, bad, "2026-11-03", self.expense_cat)
                self.assertIn("amount", ctx.exception.errors)

    def test_bad_dates_rejected(self):
        for bad in ["", "03/11/2026", "2026-13-01", "2026-02-30", "1999-01-01", "20261103"]:
            with self.subTest(date=bad):
                with self.assertRaises(ValidationError) as ctx:
                    income.add_income(self.alice.user_id, 100, bad, self.income_cat)
                self.assertIn("transaction_date", ctx.exception.errors)

    def test_required_fields_reported_together(self):
        with self.assertRaises(ValidationError) as ctx:
            income.add_income(self.alice.user_id, "", "", "")
        self.assertEqual(set(ctx.exception.errors), {"amount", "transaction_date", "category_id"})

    def test_category_type_must_match(self):
        uid = self.alice.user_id
        with self.assertRaises(ValidationError) as ctx:
            expenses.add_expense(uid, 100, "2026-11-03", self.income_cat)
        self.assertIn("category_id", ctx.exception.errors)
        with self.assertRaises(ValidationError):
            income.add_income(uid, 100, "2026-11-03", self.expense_cat)

    def test_cannot_use_another_users_category(self):
        bobs = categories.add_category(self.bob.user_id, "Bobs secret", "expense")
        with self.assertRaises(ValidationError):
            expenses.add_expense(self.alice.user_id, 100, "2026-11-03", bobs.category_id)

    def test_users_cannot_touch_each_others_records(self):
        rec = expenses.add_expense(self.alice.user_id, 100, "2026-11-03", self.expense_cat)
        bid = self.bob.user_id
        with self.assertRaises(NotFoundError):
            expenses.get_expense(bid, rec.transaction_id)
        with self.assertRaises(NotFoundError):
            expenses.update_expense(bid, rec.transaction_id, 1, "2026-11-03", self.cat("Food", "expense", self.bob))
        with self.assertRaises(NotFoundError):
            expenses.delete_expense(bid, rec.transaction_id)
        with self.assertRaises(NotFoundError):
            transactions.get_transaction(bid, rec.transaction_id)
        self.assertEqual(expenses.list_expenses(bid), [])
        self.assertEqual(expenses.get_expense(self.alice.user_id, rec.transaction_id).amount, 100.0)

    def test_income_id_is_not_reachable_through_expense_operations(self):
        rec = income.add_income(self.alice.user_id, 100, "2026-11-03", self.income_cat)
        with self.assertRaises(NotFoundError):
            expenses.get_expense(self.alice.user_id, rec.transaction_id)

    def test_database_trigger_blocks_wrong_category_type(self):
        from database import db_connection as db
        from modules.errors import DatabaseError
        with self.assertRaises(DatabaseError):
            db.execute("INSERT INTO transactions (user_id, category_id, transaction_type, amount, "
                       "transaction_date) VALUES (?, ?, 'expense', 10, '2026-11-01')",
                       (self.alice.user_id, self.income_cat))

    def test_polymorphic_signed_amount(self):
        uid = self.alice.user_id
        inc = income.add_income(uid, 100, "2026-11-01", self.income_cat)
        exp = expenses.add_expense(uid, 30, "2026-11-02", self.expense_cat)
        self.assertEqual((inc.signed_amount(), exp.signed_amount()), (100, -30))
        self.assertEqual(transactions.summarize([inc, exp])["net"], 70)


class HistoryTests(FinanceTestCase):
    def setUp(self):
        super().setUp()
        uid = self.alice.user_id
        self.other_exp = self.cat("Transport", "expense")
        income.add_income(uid, 10000, "2026-10-05", self.income_cat, "October salary")
        income.add_income(uid, 12000, "2026-11-05", self.income_cat, "November salary")
        expenses.add_expense(uid, 500, "2026-10-10", self.expense_cat, "Groceries 100% fresh")
        expenses.add_expense(uid, 150, "2026-11-10", self.other_exp, "Matatu")
        expenses.add_expense(uid, 900, "2026-11-20", self.expense_cat, "Dinner out")

    def test_combined_history_newest_first(self):
        dates = [t.transaction_date for t in transactions.search_transactions(self.alice.user_id)]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertEqual(len(dates), 5)

    def test_filters(self):
        uid = self.alice.user_id
        self.assertEqual(len(transactions.search_transactions(uid, txn_type="income")), 2)
        self.assertEqual(len(transactions.search_transactions(uid, category_id=self.expense_cat)), 2)
        self.assertEqual(len(transactions.search_transactions(uid, date_from="2026-11-01", date_to="2026-11-30")), 3)

    def test_text_search_and_wildcards_are_literal(self):
        uid = self.alice.user_id
        self.assertEqual(len(transactions.search_transactions(uid, text="dinner")), 1)
        self.assertEqual(len(transactions.search_transactions(uid, text="100%")), 1)
        self.assertEqual(len(transactions.search_transactions(uid, text="%")), 1)
        self.assertEqual(len(transactions.search_transactions(uid, text="_")), 0)

    def test_sorting(self):
        uid = self.alice.user_id
        amounts = [t.amount for t in transactions.search_transactions(uid, sort="amount", direction="desc")]
        self.assertEqual(amounts, sorted(amounts, reverse=True))
        amounts = [t.amount for t in transactions.search_transactions(uid, sort="amount", direction="asc")]
        self.assertEqual(amounts, sorted(amounts))

    def test_parse_filters(self):
        f = transactions.parse_filters({"type": "expense", "month": "2026-11", "q": "  dinner  ", "sort": "amount", "dir": "asc"})
        self.assertEqual((f["txn_type"], f["date_from"], f["date_to"], f["text"]), ("expense", "2026-11-01", "2026-11-30", "dinner"))
        self.assertEqual((f["sort"], f["direction"]), ("amount", "asc"))
        for bad in ({"type": "loan"}, {"month": "2026-13"}, {"from": "x"}, {"category": "abc"},
                    {"from": "2026-12-01", "to": "2026-11-01"}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError):
                    transactions.parse_filters(bad)
        self.assertEqual(transactions.parse_filters({"sort": "hack"})["sort"], "date")

    def test_edit_and_delete_route_to_right_operation(self):
        uid = self.alice.user_id
        for t in transactions.search_transactions(uid):
            cat = self.income_cat if t.transaction_type == "income" else self.expense_cat
            updated = transactions.update_transaction(uid, t.transaction_id, 1, "2026-11-01", cat, "x")
            self.assertEqual(type(updated), type(t))
        victim = transactions.search_transactions(uid)[0]
        transactions.delete_transaction(uid, victim.transaction_id)
        self.assertEqual(len(transactions.search_transactions(uid)), 4)
