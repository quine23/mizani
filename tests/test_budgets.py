from modules import budgets, categories, expenses, income
from modules.errors import NotFoundError, ValidationError
from tests.base import FinanceTestCase


class BudgetTests(FinanceTestCase):
    def test_category_budget_remaining_and_status(self):
        uid = self.alice.user_id
        budgets.set_budget(uid, 1000, 11, 2026, self.expense_cat)
        expenses.add_expense(uid, 500, "2026-11-05", self.expense_cat)
        b = budgets.list_budgets(uid, 11, 2026)[0]
        self.assertEqual((b.spent, b.remaining, b.percent_used, b.status), (500, 500, 50.0, "ok"))
        expenses.add_expense(uid, 300, "2026-11-06", self.expense_cat)
        self.assertEqual(budgets.list_budgets(uid, 11, 2026)[0].status, "warning")  # 80% reached
        expenses.add_expense(uid, 300, "2026-11-07", self.expense_cat)
        b = budgets.list_budgets(uid, 11, 2026)[0]
        self.assertEqual((b.status, b.overspent_by, b.remaining), ("exceeded", 100, -100))

    def test_only_matching_month_and_category_counted(self):
        uid = self.alice.user_id
        transport = self.cat("Transport", "expense")
        budgets.set_budget(uid, 1000, 11, 2026, self.expense_cat)
        expenses.add_expense(uid, 400, "2026-10-31", self.expense_cat)   # other month
        expenses.add_expense(uid, 400, "2026-11-01", transport)          # other category
        income.add_income(uid, 5000, "2026-11-02", self.income_cat)      # income never counts
        self.assertEqual(budgets.list_budgets(uid, 11, 2026)[0].spent, 0)

    def test_overall_budget_counts_all_expenses(self):
        uid = self.alice.user_id
        budgets.set_budget(uid, 2000, 11, 2026)
        expenses.add_expense(uid, 400, "2026-11-01", self.expense_cat)
        expenses.add_expense(uid, 600, "2026-11-02", self.cat("Transport", "expense"))
        b = budgets.list_budgets(uid, 11, 2026)[0]
        self.assertEqual((b.label, b.spent, b.remaining), ("Overall monthly budget", 1000, 1000))

    def test_setting_again_replaces_limit(self):
        uid = self.alice.user_id
        budgets.set_budget(uid, 1000, 11, 2026, self.expense_cat)
        budgets.set_budget(uid, 1500, 11, 2026, self.expense_cat)
        budgets.set_budget(uid, 3000, 11, 2026)
        budgets.set_budget(uid, 3500, 11, 2026)
        listed = budgets.list_budgets(uid, 11, 2026)
        self.assertEqual(sorted(b.amount for b in listed), [1500, 3500])

    def test_alerts_only_for_warning_or_exceeded(self):
        uid = self.alice.user_id
        budgets.set_budget(uid, 1000, 11, 2026, self.expense_cat)
        budgets.set_budget(uid, 1000, 11, 2026, self.cat("Transport", "expense"))
        expenses.add_expense(uid, 950, "2026-11-01", self.expense_cat)
        alerts = budgets.budget_alerts(uid, 11, 2026)
        self.assertEqual([a.label for a in alerts], ["Food"])

    def test_validation(self):
        uid = self.alice.user_id
        for kwargs in [dict(amount=0, month=11, year=2026), dict(amount=100, month=13, year=2026),
                       dict(amount=100, month=11, year=1980), dict(amount="x", month=11, year=2026),
                       dict(amount=100, month=11, year=2026, category_id=self.income_cat),
                       dict(amount=100, month=11, year=2026, category_id=99999)]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValidationError):
                    budgets.set_budget(uid, **kwargs)

    def test_isolation_between_users(self):
        b = budgets.set_budget(self.alice.user_id, 1000, 11, 2026)
        self.assertEqual(budgets.list_budgets(self.bob.user_id, 11, 2026), [])
        with self.assertRaises(NotFoundError):
            budgets.delete_budget(self.bob.user_id, b.budget_id)
        with self.assertRaises(ValidationError):  # Bob cannot budget on Alice's private category
            mine = categories.add_category(self.alice.user_id, "Pets", "expense")
            budgets.set_budget(self.bob.user_id, 100, 11, 2026, mine.category_id)

    def test_delete(self):
        b = budgets.set_budget(self.alice.user_id, 1000, 11, 2026)
        budgets.delete_budget(self.alice.user_id, b.budget_id)
        self.assertEqual(budgets.list_budgets(self.alice.user_id, 11, 2026), [])
