"""Mizani - Personal Finance and Expense Management System (Flask web app).

Run with:  python app.py   then open http://127.0.0.1:5000
The routes below only read the request, call the module that owns the feature,
and render a template. All rules live in the modules/ package.
"""
import hmac
import logging
import os
import secrets
from datetime import date
from functools import wraps

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from markupsafe import Markup

from database import db_connection as db
from modules import (authentication, budgets, categories, charts, exports,
                     expenses, income, reports, transactions)
from modules.errors import (AuthenticationError, DatabaseError, NotFoundError,
                            ValidationError)
from modules.formatting import MONTH_NAMES, format_money, period_label
from modules.validators import month_bounds

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")

# One table drives the income and expense pages, so they share the same routes.
KINDS = {
    "income": {
        "type": "income", "title": "Income", "singular": "income",
        "list": income.list_income, "get": income.get_income, "add": income.add_income,
        "update": income.update_income, "delete": income.delete_income,
    },
    "expenses": {
        "type": "expense", "title": "Expenses", "singular": "expense",
        "list": expenses.list_expenses, "get": expenses.get_expense, "add": expenses.add_expense,
        "update": expenses.update_expense, "delete": expenses.delete_expense,
    },
}
KIND_BY_TYPE = {"income": "income", "expense": "expenses"}


def _load_secret_key():
    """Use SECRET_KEY if set, otherwise create one once and keep it out of Git."""
    from_env = os.environ.get("SECRET_KEY")
    if from_env:
        return from_env
    path = os.path.join(INSTANCE_DIR, "secret_key")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except FileNotFoundError:
        os.makedirs(INSTANCE_DIR, exist_ok=True)
        key = secrets.token_hex(32)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(key)
        return key


def shift_period(month, year, delta):
    total = year * 12 + (month - 1) + delta
    return total % 12 + 1, total // 12


def get_period():
    """Month and year from ?month=&year=, falling back to the current month."""
    today = date.today()
    try:
        month = int(request.args.get("month", today.month))
        year = int(request.args.get("year", today.year))
    except ValueError:
        return today.month, today.year
    if not (1 <= month <= 12 and 2000 <= year <= 2100):
        return today.month, today.year
    return month, year


def period_context(month, year):
    prev_m, prev_y = shift_period(month, year, -1)
    next_m, next_y = shift_period(month, year, 1)
    return {
        "month": month, "year": year, "label": period_label(month, year),
        "prev": {"month": prev_m, "year": prev_y},
        "next": {"month": next_m, "year": next_y},
    }


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=_load_secret_key(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        CSRF_ENABLED=True,
        DATABASE=None,
    )
    if test_config:
        app.config.update(test_config)
    if app.config["DATABASE"]:
        db.set_db_path(app.config["DATABASE"])
    db.init_db()

    # ---------------------------------------------------------------- helpers
    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                flash("Please log in to continue.", "info")
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    def form_errors(exc):
        return exc.errors if isinstance(exc, ValidationError) else {}

    @app.before_request
    def load_user_and_check_csrf():
        g.user = None
        user_id = session.get("user_id")
        if user_id is not None:
            try:
                g.user = authentication.get_user(user_id)
            except NotFoundError:
                session.clear()
        if request.method == "POST" and app.config["CSRF_ENABLED"]:
            sent = request.form.get("csrf_token", "")
            expected = session.get("csrf_token")
            if not expected or not hmac.compare_digest(sent, expected):
                abort(400, description="Your session expired. Go back, refresh the page and try again.")

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    @app.context_processor
    def template_helpers():
        return {
            "csrf_input": lambda: Markup(
                f'<input type="hidden" name="csrf_token" value="{csrf_token()}">'),
            "today": date.today().isoformat(),
            "month_names": MONTH_NAMES,
        }

    app.jinja_env.filters["money"] = format_money

    @app.errorhandler(NotFoundError)
    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, title="Page not found",
                               message="That page or record does not exist, or it is not yours."), 404

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("error.html", code=400, title="Request not accepted",
                               message=getattr(error, "description", "Bad request.")), 400

    @app.errorhandler(DatabaseError)
    def database_failed(error):
        app.logger.error("Database error: %s", error)
        return render_template("error.html", code=500, title="Something went wrong",
                               message="The database could not complete that action. Try again."), 500

    # ---------------------------------------------------------- authentication
    @app.route("/")
    def index():
        return redirect(url_for("dashboard" if g.user else "login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if g.user:
            return redirect(url_for("dashboard"))
        form, errors = {}, {}
        if request.method == "POST":
            form = request.form
            try:
                user = authentication.register_user(
                    form.get("full_name"), form.get("email"),
                    form.get("password"), form.get("confirm_password"))
            except ValidationError as exc:
                errors = exc.errors
            else:
                session.clear()
                session["user_id"] = user.user_id
                flash(f"Welcome, {user.first_name}. Your account is ready.", "success")
                return redirect(url_for("dashboard"))
        return render_template("register.html", form=form, errors=errors), (400 if errors else 200)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("dashboard"))
        form, error = {}, None
        if request.method == "POST":
            form = request.form
            try:
                user = authentication.login_user(form.get("email"), form.get("password"))
            except AuthenticationError as exc:
                error = str(exc)
            else:
                session.clear()
                session["user_id"] = user.user_id
                return redirect(url_for("dashboard"))
        return render_template("login.html", form=form, error=error), (400 if error else 200)

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("login"))

    # --------------------------------------------------------------- dashboard
    @app.route("/dashboard")
    @login_required
    def dashboard():
        month, year = get_period()
        first, last = month_bounds(month, year)
        data = reports.dashboard(g.user.user_id, month, year)
        recent = transactions.search_transactions(g.user.user_id)[:6]
        return render_template("dashboard.html", data=data, recent=recent,
                               period=period_context(month, year))

    # ------------------------------------------------- income and expenses
    @app.route("/<any(income,expenses):kind>")
    @login_required
    def kind_list(kind):
        spec = KINDS[kind]
        month, year = get_period()
        first, last = month_bounds(month, year)
        items = spec["list"](g.user.user_id, date_from=first, date_to=last)
        return render_template("kind_list.html", kind=kind, spec=spec, items=items,
                               total=round(sum(t.amount for t in items), 2),
                               period=period_context(month, year))

    def render_kind_form(kind, spec, form, errors, txn=None):
        status = 400 if errors else 200
        return render_template(
            "kind_form.html", kind=kind, spec=spec, form=form, errors=errors, txn=txn,
            categories=categories.list_categories(g.user.user_id, spec["type"])), status

    @app.route("/<any(income,expenses):kind>/new", methods=["GET", "POST"])
    @login_required
    def kind_new(kind):
        spec = KINDS[kind]
        form, errors = {}, {}
        if request.method == "POST":
            form = request.form
            try:
                spec["add"](g.user.user_id, form.get("amount"), form.get("transaction_date"),
                            form.get("category_id"), form.get("description"))
            except ValidationError as exc:
                errors = exc.errors
            else:
                flash(f"{spec['title']} record added.", "success")
                return redirect(url_for("kind_list", kind=kind))
        return render_kind_form(kind, spec, form, errors)

    @app.route("/<any(income,expenses):kind>/<int:txn_id>/edit", methods=["GET", "POST"])
    @login_required
    def kind_edit(kind, txn_id):
        spec = KINDS[kind]
        txn = spec["get"](g.user.user_id, txn_id)
        form, errors = {
            "amount": f"{txn.amount:.2f}", "transaction_date": txn.transaction_date,
            "category_id": str(txn.category_id), "description": txn.description,
        }, {}
        if request.method == "POST":
            form = request.form
            try:
                spec["update"](g.user.user_id, txn_id, form.get("amount"),
                               form.get("transaction_date"), form.get("category_id"),
                               form.get("description"))
            except ValidationError as exc:
                errors = exc.errors
            else:
                flash(f"{spec['title']} record updated.", "success")
                return redirect(url_for("kind_list", kind=kind))
        return render_kind_form(kind, spec, form, errors, txn)

    @app.route("/<any(income,expenses):kind>/<int:txn_id>/delete", methods=["GET", "POST"])
    @login_required
    def kind_delete(kind, txn_id):
        spec = KINDS[kind]
        txn = spec["get"](g.user.user_id, txn_id)
        if request.method == "POST":
            spec["delete"](g.user.user_id, txn_id)
            flash(f"{spec['title']} record deleted.", "success")
            return redirect(url_for("kind_list", kind=kind))
        return render_template(
            "confirm_delete.html", heading=f"Delete this {spec['singular']} record?",
            detail=f"{txn.transaction_date} - {txn.category_name} - {format_money(txn.amount)}"
                   + (f" - {txn.description}" if txn.description else ""),
            cancel_url=url_for("kind_list", kind=kind))

    # ------------------------------------------------ combined transactions
    @app.route("/transactions")
    @login_required
    def transactions_page():
        filters, errors = {}, {}
        try:
            filters = transactions.parse_filters(request.args)
        except ValidationError as exc:
            errors = exc.errors
            filters = transactions.parse_filters({})
        items = transactions.search_transactions(g.user.user_id, **filters)
        return render_template(
            "transactions.html", items=items, errors=errors,
            totals=transactions.summarize(items),
            categories=categories.list_categories(g.user.user_id),
            args=request.args, export_query=request.query_string.decode("utf-8"),
            kind_by_type=KIND_BY_TYPE)

    @app.route("/transactions/<int:txn_id>")
    @login_required
    def transaction_detail(txn_id):
        txn = transactions.get_transaction(g.user.user_id, txn_id)
        return render_template("transaction_detail.html", txn=txn,
                               kind=KIND_BY_TYPE[txn.transaction_type])

    @app.route("/transactions/<int:txn_id>/edit")
    @login_required
    def transaction_edit(txn_id):
        txn = transactions.get_transaction(g.user.user_id, txn_id)
        return redirect(url_for("kind_edit", kind=KIND_BY_TYPE[txn.transaction_type], txn_id=txn_id))

    @app.route("/transactions/<int:txn_id>/delete")
    @login_required
    def transaction_delete(txn_id):
        txn = transactions.get_transaction(g.user.user_id, txn_id)
        return redirect(url_for("kind_delete", kind=KIND_BY_TYPE[txn.transaction_type], txn_id=txn_id))

    # -------------------------------------------------------------- categories
    @app.route("/categories", methods=["GET", "POST"])
    @login_required
    def categories_page():
        form, errors = {}, {}
        if request.method == "POST":
            form = request.form
            try:
                added = categories.add_category(g.user.user_id, form.get("name"),
                                                form.get("category_type"))
            except ValidationError as exc:
                errors = exc.errors
            else:
                flash(f"Category '{added.name}' added.", "success")
                return redirect(url_for("categories_page"))
        all_categories = categories.list_categories(g.user.user_id)
        return render_template(
            "categories.html", form=form, errors=errors,
            income_categories=[c for c in all_categories if c.category_type == "income"],
            expense_categories=[c for c in all_categories if c.category_type == "expense"],
        ), (400 if errors else 200)

    @app.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
    @login_required
    def category_edit(category_id):
        category = categories.get_category(g.user.user_id, category_id)
        errors, name = {}, category.name
        if request.method == "POST":
            name = request.form.get("name", "")
            try:
                categories.rename_category(g.user.user_id, category_id, name)
            except ValidationError as exc:
                errors = exc.errors
            else:
                flash("Category renamed.", "success")
                return redirect(url_for("categories_page"))
        return render_template("category_edit.html", category=category, name=name,
                               errors=errors), (400 if errors else 200)

    @app.route("/categories/<int:category_id>/delete", methods=["GET", "POST"])
    @login_required
    def category_delete(category_id):
        category = categories.get_category(g.user.user_id, category_id)
        error = None
        if request.method == "POST":
            try:
                categories.delete_category(g.user.user_id, category_id)
            except ValidationError as exc:
                error = " ".join(exc.errors.values())
            else:
                flash(f"Category '{category.name}' deleted.", "success")
                return redirect(url_for("categories_page"))
        return render_template(
            "confirm_delete.html", heading="Delete this category?",
            detail=f"{category.name} ({category.category_type})",
            cancel_url=url_for("categories_page"), error=error), (400 if error else 200)

    # ----------------------------------------------------------------- budgets
    @app.route("/budgets", methods=["GET", "POST"])
    @login_required
    def budgets_page():
        errors, form = {}, {}
        if request.method == "POST":
            form = request.form
            try:
                saved = budgets.set_budget(
                    g.user.user_id, form.get("amount"), form.get("month"),
                    form.get("year"), form.get("category_id"))
            except ValidationError as exc:
                errors = exc.errors
                month, year = get_period()
            else:
                flash(f"Budget saved: {saved.label}, {format_money(saved.amount)}.", "success")
                return redirect(url_for("budgets_page", month=saved.month, year=saved.year))
        else:
            month, year = get_period()
        if errors:
            try:
                month, year = int(form.get("month")), int(form.get("year"))
                month_bounds(month, year)
            except (TypeError, ValueError):
                month, year = date.today().month, date.today().year
        return render_template(
            "budgets.html", items=budgets.list_budgets(g.user.user_id, month, year),
            period=period_context(month, year), errors=errors, form=form,
            expense_categories=categories.list_categories(g.user.user_id, "expense"),
        ), (400 if errors else 200)

    @app.route("/budgets/<int:budget_id>/delete", methods=["GET", "POST"])
    @login_required
    def budget_delete(budget_id):
        budget = budgets.get_budget(g.user.user_id, budget_id)
        back = url_for("budgets_page", month=budget.month, year=budget.year)
        if request.method == "POST":
            budgets.delete_budget(g.user.user_id, budget_id)
            flash("Budget deleted.", "success")
            return redirect(back)
        return render_template(
            "confirm_delete.html", heading="Delete this budget?",
            detail=f"{budget.label}: {format_money(budget.amount)} for "
                   f"{period_label(budget.month, budget.year)}", cancel_url=back)

    # ----------------------------------------------------------------- reports
    @app.route("/reports")
    @login_required
    def reports_page():
        month, year = get_period()
        summary = reports.monthly_summary(g.user.user_id, month, year)
        return render_template(
            "reports.html", summary=summary, period=period_context(month, year),
            insights=reports.insights(g.user.user_id, month, year),
            budgets=budgets.list_budgets(g.user.user_id, month, year),
            yearly=reports.monthly_series(g.user.user_id, year))

    def png(data):
        response = Response(data, mimetype="image/png")
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.route("/charts/monthly.png")
    @login_required
    def chart_monthly():
        _month, year = get_period()
        return png(charts.monthly_chart_png(reports.monthly_series(g.user.user_id, year), year))

    @app.route("/charts/categories.png")
    @login_required
    def chart_categories():
        month, year = get_period()
        rows = reports.category_breakdown(g.user.user_id, "expense", month, year)
        return png(charts.category_chart_png(rows, f"Spending by category, {period_label(month, year)}"))

    # ------------------------------------------------------------------ export
    @app.route("/export/<any(csv,xlsx):file_format>")
    @login_required
    def export(file_format):
        try:
            filters = transactions.parse_filters(request.args)
        except ValidationError:
            flash("Some filters were not valid, so nothing was exported.", "error")
            return redirect(url_for("transactions_page"))
        items = transactions.search_transactions(g.user.user_id, **filters)
        name = f"mizani_transactions_{date.today().isoformat()}.{file_format}"
        headers = {"Content-Disposition": f'attachment; filename="{name}"'}
        if file_format == "csv":
            body = exports.export_csv(items).encode("utf-8-sig")
            return Response(body, mimetype="text/csv", headers=headers)
        body = exports.export_excel(items)
        return Response(body, headers=headers, mimetype=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
