import csv
import io

from modules import charts, exports, expenses, income, reports, transactions
from tests.base import FinanceTestCase


class ReportTests(FinanceTestCase):
    def setUp(self):
        super().setUp()
        uid = self.alice.user_id
        self.transport = self.cat("Transport", "expense")
        income.add_income(uid, 20000, "2026-10-01", self.income_cat)
        income.add_income(uid, 25000.50, "2026-11-01", self.income_cat)
        expenses.add_expense(uid, 2000, "2026-10-10", self.expense_cat)
        expenses.add_expense(uid, 3000, "2026-11-10", self.expense_cat)
        expenses.add_expense(uid, 1000, "2026-11-12", self.transport)
        income.add_income(self.bob.user_id, 999999, "2026-11-01", self.cat("Salary", "income", self.bob))

    def test_totals_and_balance(self):
        t = reports.totals(self.alice.user_id)
        self.assertEqual((t["income"], t["expenses"], t["balance"]), (45000.5, 6000, 39000.5))

    def test_totals_ignore_other_users(self):
        self.assertEqual(reports.totals(self.bob.user_id)["income"], 999999)

    def test_monthly_summary(self):
        s = reports.monthly_summary(self.alice.user_id, 11, 2026)
        self.assertEqual((s["income"], s["expenses"], s["net"], s["transaction_count"]), (25000.5, 4000, 21000.5, 3))
        self.assertEqual(s["savings_rate"], 84.0)
        self.assertEqual(s["top_expense_category"]["name"], "Food")
        self.assertEqual([(c["name"], c["total"], c["share"]) for c in s["expense_categories"]],
                         [("Food", 3000, 75.0), ("Transport", 1000, 25.0)])

    def test_empty_month_has_no_savings_rate(self):
        s = reports.monthly_summary(self.alice.user_id, 1, 2026)
        self.assertEqual((s["income"], s["expenses"], s["savings_rate"]), (0, 0, None))
        self.assertEqual(len(reports.insights(self.alice.user_id, 1, 2026)), 1)

    def test_monthly_series_matches_transactions(self):
        series = reports.monthly_series(self.alice.user_id, 2026)
        self.assertEqual(len(series), 12)
        self.assertEqual((series[9]["income"], series[9]["expenses"]), (20000, 2000))
        self.assertEqual((series[10]["income"], series[10]["expenses"], series[10]["net"]), (25000.5, 4000, 21000.5))
        self.assertEqual(series[0]["income"], 0)

    def test_insights_compare_with_previous_month(self):
        text = " ".join(reports.insights(self.alice.user_id, 11, 2026))
        self.assertIn("100.0% higher than October", text)
        self.assertIn("Food", text)

    def test_charts_return_png(self):
        png = charts.monthly_chart_png(reports.monthly_series(self.alice.user_id, 2026), 2026)
        self.assertTrue(png.startswith(b"\x89PNG"))
        rows = reports.category_breakdown(self.alice.user_id, "expense", 11, 2026)
        self.assertTrue(charts.category_chart_png(rows, "t").startswith(b"\x89PNG"))
        self.assertTrue(charts.category_chart_png([], "empty").startswith(b"\x89PNG"))


class ExportTests(FinanceTestCase):
    def setUp(self):
        super().setUp()
        uid = self.alice.user_id
        income.add_income(uid, 1500.5, "2026-11-01", self.income_cat, "Pay, with comma")
        expenses.add_expense(uid, 99, "2026-11-02", self.expense_cat, "=HYPERLINK(\"evil\")")
        self.items = transactions.search_transactions(uid)

    def test_csv_round_trip(self):
        rows = list(csv.reader(io.StringIO(exports.export_csv(self.items))))
        self.assertEqual(rows[0], exports.HEADERS)
        self.assertEqual(len(rows), 3)
        by_type = {r[1]: r for r in rows[1:]}
        self.assertEqual(by_type["Income"][3:], ["Pay, with comma", "1500.50"])
        self.assertEqual(by_type["Expense"][4], "99.00")

    def test_csv_blocks_formula_injection(self):
        rows = list(csv.reader(io.StringIO(exports.export_csv(self.items))))
        description = [r for r in rows if r[1] == "Expense"][0][3]
        self.assertTrue(description.startswith("'="))

    def test_excel_file_opens_and_matches(self):
        from openpyxl import load_workbook
        sheet = load_workbook(io.BytesIO(exports.export_excel(self.items))).active
        values = list(sheet.values)
        self.assertEqual(values[0], tuple(exports.HEADERS))
        self.assertEqual(len(values), 3)
        self.assertEqual(sorted(v[4] for v in values[1:]), [99, 1500.5])

    def test_export_only_contains_filtered_records(self):
        only_income = transactions.search_transactions(self.alice.user_id, txn_type="income")
        self.assertEqual(len(list(csv.reader(io.StringIO(exports.export_csv(only_income))))), 2)
