"""End-to-end tests that drive the real Flask app through its web routes."""
import csv
import io
import os
import re
import shutil
import tempfile
import unittest

import app as app_module
from modules import authentication
from tests import base  # noqa: F401  (sets the fast password hashing for tests)


class WebTestCase(unittest.TestCase):
    csrf = False

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = app_module.create_app({
            "TESTING": True, "CSRF_ENABLED": self.csrf,
            "DATABASE": os.path.join(self.tmp, "web.db"), "SECRET_KEY": "test-key"})
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def register(self, client=None, name="Alice Wanjiru", email="alice@example.com", password="Passw0rd1"):
        return (client or self.client).post("/register", data={
            "full_name": name, "email": email, "password": password, "confirm_password": password})

    def login(self, client, email, password="Passw0rd1"):
        return client.post("/login", data={"email": email, "password": password})

    def second_client(self):
        other = self.app.test_client()
        self.register(other, "Bob Otieno", "bob@example.com")
        return other

    def category_id(self, client, kind, name):
        html = client.get(f"/{'income' if kind == 'income' else 'expenses'}/new").get_data(as_text=True)
        match = re.search(r'<option value="(\d+)"[^>]*>' + re.escape(name), html)
        self.assertIsNotNone(match, f"{name} not offered for {kind}")
        return match.group(1)


class PageFlowTests(WebTestCase):
    def test_protected_pages_redirect_to_login(self):
        for path in ["/dashboard", "/transactions", "/income", "/expenses", "/categories",
                     "/budgets", "/reports", "/export/csv", "/charts/monthly.png"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

    def test_register_login_logout(self):
        response = self.register()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/dashboard").status_code, 200)
        self.assertEqual(self.client.post("/logout").status_code, 302)
        self.assertEqual(self.client.get("/dashboard").status_code, 302)
        self.assertEqual(self.login(self.client, "alice@example.com").status_code, 302)
        self.assertEqual(self.client.get("/dashboard").status_code, 200)

    def test_bad_login_and_duplicate_registration(self):
        self.register()
        self.client.post("/logout")
        bad = self.login(self.client, "alice@example.com", "wrong-pass1")
        self.assertEqual(bad.status_code, 400)
        self.assertIn("Invalid email or password", bad.get_data(as_text=True))
        dup = self.register(self.app.test_client())
        self.assertEqual(dup.status_code, 400)
        self.assertIn("already exists", dup.get_data(as_text=True))

    def test_every_page_renders_for_a_logged_in_user(self):
        self.register()
        for path in ["/dashboard", "/transactions", "/income", "/expenses", "/income/new",
                     "/expenses/new", "/categories", "/budgets", "/reports",
                     "/dashboard?month=2&year=2026", "/reports?month=99&year=abc"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_income_expense_full_flow_and_dashboard_numbers(self):
        self.register()
        c = self.client
        inc_cat = self.category_id(c, "income", "Salary")
        exp_cat = self.category_id(c, "expense", "Food")
        c.post("/income/new", data={"amount": "50000", "transaction_date": "2026-11-01", "category_id": inc_cat, "description": "Pay"})
        c.post("/expenses/new", data={"amount": "1250.50", "transaction_date": "2026-11-02", "category_id": exp_cat, "description": "Lunch"})
        html = c.get("/dashboard?month=11&year=2026").get_data(as_text=True)
        self.assertIn("KES 48,749.50", html)   # balance
        self.assertIn("KES 50,000.00", html)
        self.assertIn("KES 1,250.50", html)
        listing = c.get("/expenses?month=11&year=2026").get_data(as_text=True)
        self.assertIn("Lunch", listing)
        txn_id = re.search(r"/expenses/(\d+)/edit", listing).group(1)
        edit = c.post(f"/expenses/{txn_id}/edit", data={"amount": "2000", "transaction_date": "2026-11-02", "category_id": exp_cat, "description": "Big lunch"})
        self.assertEqual(edit.status_code, 302)
        self.assertIn("Big lunch", c.get("/expenses?month=11&year=2026").get_data(as_text=True))
        confirm = c.get(f"/expenses/{txn_id}/delete")
        self.assertIn("cannot be undone", confirm.get_data(as_text=True))
        self.assertIn("Big lunch", c.get("/expenses?month=11&year=2026").get_data(as_text=True))  # GET did not delete
        c.post(f"/expenses/{txn_id}/delete")
        self.assertNotIn("Big lunch", c.get("/expenses?month=11&year=2026").get_data(as_text=True))

    def test_form_errors_are_shown_and_input_kept(self):
        self.register()
        response = self.client.post("/expenses/new", data={"amount": "-5", "transaction_date": "2026-11-02", "category_id": "", "description": "keep me"})
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 400)
        self.assertIn("greater than zero", html)
        self.assertIn("Choose a category", html)
        self.assertIn('value="keep me"', html)

    def test_expense_cannot_use_income_category_via_web(self):
        self.register()
        inc_cat = self.category_id(self.client, "income", "Salary")
        response = self.client.post("/expenses/new", data={"amount": "10", "transaction_date": "2026-11-02", "category_id": inc_cat})
        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be used for expense", response.get_data(as_text=True))

    def test_search_filter_and_export(self):
        self.register()
        c = self.client
        exp_cat = self.category_id(c, "expense", "Food")
        inc_cat = self.category_id(c, "income", "Salary")
        c.post("/expenses/new", data={"amount": "100", "transaction_date": "2026-11-02", "category_id": exp_cat, "description": "Pizza night"})
        c.post("/income/new", data={"amount": "900", "transaction_date": "2026-10-02", "category_id": inc_cat, "description": "Gift money"})
        html = c.get("/transactions?q=pizza").get_data(as_text=True)
        self.assertIn("Pizza night", html)
        self.assertNotIn("Gift money", html)
        self.assertIn("Gift money", c.get("/transactions?type=income&month=2026-10").get_data(as_text=True))
        self.assertIn("Choose a month", c.get("/transactions?month=bad").get_data(as_text=True))
        csv_response = c.get("/export/csv?type=expense")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("attachment", csv_response.headers["Content-Disposition"])
        rows = list(csv.reader(io.StringIO(csv_response.data.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][3], "Pizza night")
        xlsx = c.get("/export/xlsx")
        self.assertEqual(xlsx.status_code, 200)
        self.assertTrue(xlsx.data.startswith(b"PK"))

    def test_budget_warning_appears_on_dashboard(self):
        self.register()
        c = self.client
        exp_cat = self.category_id(c, "expense", "Food")
        c.post("/budgets", data={"amount": "1000", "month": "11", "year": "2026", "category_id": exp_cat})
        c.post("/expenses/new", data={"amount": "850", "transaction_date": "2026-11-02", "category_id": exp_cat})
        html = c.get("/dashboard?month=11&year=2026").get_data(as_text=True)
        self.assertIn("Warning: 85.0% used", html)
        c.post("/expenses/new", data={"amount": "300", "transaction_date": "2026-11-03", "category_id": exp_cat})
        self.assertIn("Over budget by KES 150.00", c.get("/budgets?month=11&year=2026").get_data(as_text=True))

    def test_categories_add_rename_delete(self):
        self.register()
        c = self.client
        c.post("/categories", data={"name": "Pet care", "category_type": "expense"})
        html = c.get("/categories").get_data(as_text=True)
        self.assertIn("Pet care", html)
        cat_id = re.search(r"/categories/(\d+)/edit", html).group(1)
        c.post(f"/categories/{cat_id}/edit", data={"name": "Pets"})
        self.assertIn("Pets", c.get("/categories").get_data(as_text=True))
        c.post(f"/categories/{cat_id}/delete")
        self.assertNotIn("<span>Pets", c.get("/categories").get_data(as_text=True))
        dup = c.post("/categories", data={"name": "food", "category_type": "expense"})
        self.assertEqual(dup.status_code, 400)

    def test_charts_are_png(self):
        self.register()
        for path in ["/charts/monthly.png", "/charts/categories.png?month=11&year=2026"]:
            response = self.client.get(path)
            self.assertEqual(response.mimetype, "image/png")
            self.assertTrue(response.data.startswith(b"\x89PNG"))

    def test_data_persists_after_app_restart(self):
        self.register()
        exp_cat = self.category_id(self.client, "expense", "Food")
        self.client.post("/expenses/new", data={"amount": "42", "transaction_date": "2026-11-02", "category_id": exp_cat, "description": "Persist me"})
        restarted = app_module.create_app({"TESTING": True, "CSRF_ENABLED": False,
                                           "DATABASE": os.path.join(self.tmp, "web.db"), "SECRET_KEY": "test-key"})
        client = restarted.test_client()
        self.login(client, "alice@example.com")
        self.assertIn("Persist me", client.get("/expenses?month=11&year=2026").get_data(as_text=True))


class SecurityTests(WebTestCase):
    def test_one_user_cannot_see_or_change_another_users_records(self):
        self.register()
        exp_cat = self.category_id(self.client, "expense", "Food")
        self.client.post("/expenses/new", data={"amount": "77", "transaction_date": "2026-11-02", "category_id": exp_cat, "description": "Alice secret"})
        txn_id = re.search(r"/expenses/(\d+)/edit", self.client.get("/expenses?month=11&year=2026").get_data(as_text=True)).group(1)
        bob = self.second_client()
        bob_cat = self.category_id(bob, "expense", "Food")
        self.assertNotIn("Alice secret", bob.get("/transactions").get_data(as_text=True))
        self.assertNotIn("Alice secret", bob.get("/expenses?month=11&year=2026").get_data(as_text=True))
        for method, path in [("get", f"/transactions/{txn_id}"), ("get", f"/expenses/{txn_id}/edit"),
                             ("get", f"/expenses/{txn_id}/delete"), ("post", f"/expenses/{txn_id}/delete"),
                             ("post", f"/expenses/{txn_id}/edit"), ("get", f"/transactions/{txn_id}/edit")]:
            with self.subTest(path=path, method=method):
                response = getattr(bob, method)(path, data={"amount": "1", "transaction_date": "2026-11-02", "category_id": bob_cat})
                self.assertEqual(response.status_code, 404)
        self.assertIn("Alice secret", self.client.get("/transactions").get_data(as_text=True))
        self.assertNotIn("Alice secret", bob.get("/export/csv").data.decode("utf-8-sig"))

    def test_other_users_budget_and_category_are_not_reachable(self):
        self.register()
        self.client.post("/categories", data={"name": "Alice only", "category_type": "expense"})
        cat_id = re.search(r"/categories/(\d+)/edit", self.client.get("/categories").get_data(as_text=True)).group(1)
        self.client.post("/budgets", data={"amount": "500", "month": "11", "year": "2026", "category_id": ""})
        bob = self.second_client()
        self.assertEqual(bob.get(f"/categories/{cat_id}/edit").status_code, 404)
        self.assertEqual(bob.post(f"/categories/{cat_id}/delete").status_code, 404)
        self.assertEqual(bob.post("/budgets/1/delete").status_code, 404)
        self.assertNotIn("Alice only", bob.get("/categories").get_data(as_text=True))

    def test_html_is_escaped(self):
        self.register()
        exp_cat = self.category_id(self.client, "expense", "Food")
        self.client.post("/expenses/new", data={"amount": "5", "transaction_date": "2026-11-02", "category_id": exp_cat, "description": "<script>alert(1)</script>"})
        html = self.client.get("/transactions").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_sql_injection_attempts_are_treated_as_text(self):
        self.register()
        html = self.client.get("/transactions?q=' OR 1=1 --").get_data(as_text=True)
        self.assertIn("No transactions match", html)
        bad_login = self.login(self.app.test_client(), "alice@example.com' OR '1'='1", "x")
        self.assertEqual(bad_login.status_code, 400)


class CsrfTests(WebTestCase):
    csrf = True

    def test_post_without_token_is_rejected(self):
        response = self.client.post("/register", data={"full_name": "A B", "email": "a@b.com", "password": "Passw0rd1", "confirm_password": "Passw0rd1"})
        self.assertEqual(response.status_code, 400)

    def test_post_with_token_is_accepted(self):
        html = self.client.get("/register").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        response = self.client.post("/register", data={"csrf_token": token, "full_name": "A B", "email": "a@b.com", "password": "Passw0rd1", "confirm_password": "Passw0rd1"})
        self.assertEqual(response.status_code, 302)

    def test_logout_needs_post_and_token(self):
        self.assertEqual(self.client.get("/logout").status_code, 405)


if __name__ == "__main__":
    unittest.main()
