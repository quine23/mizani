# Mizani: Personal Finance and Expense Management System

BIT 2203 Advanced Programming Using Python, Project 9. Presentation: 24 November 2026.

Mizani lets a person register, record income and expenses, organise them in categories, set monthly budgets, search their history, see monthly reports with charts, and export their records to CSV or Excel.

## Run it

You need Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed_demo.py              # optional: demo user with three months of data
python app.py
```

Open http://127.0.0.1:5000. Demo login: `demo@example.com` / `Demo1234`.
The database is created automatically at `instance/finance.db`. Delete that file to start fresh.

## Run the tests

```bash
python -m unittest discover -s tests -t .
```

69 tests cover validation, CRUD, category rules, budgets, reports, exports, saved data, and one user trying to reach another user's records.

## Project structure

```
app.py                  Flask routes only; no business rules
seed_demo.py            demo user and sample data
database/
    schema.sql          tables, constraints, triggers
    db_connection.py    the one shared connection layer
modules/
    authentication.py   1  register, login, password hashing
    income.py           2  income CRUD
    expenses.py         3  expense CRUD
    categories.py       4  default and custom categories
    budgets.py          5  monthly budgets and warnings
    transactions.py     6  combined history, search, filter, sort
    reports.py          7  balance, monthly summary, insights
    charts.py           7  matplotlib charts
    exports.py          8  CSV and Excel export
    ledger.py              shared transaction data access (income/expenses build on it)
    models.py              User, Transaction, Income, Expense, Category, Budget
    validators.py          all input validation
    errors.py, formatting.py
templates/, static/     pages and stylesheet
tests/                  unit and end-to-end tests
```

## Who owns what (from the group plan)

| Member | Main files |
| --- | --- |
| 1 Authentication | `modules/authentication.py`, `templates/login.html`, `register.html` |
| 2 Income | `modules/income.py`, the income routes in `app.py` |
| 3 Expenses | `modules/expenses.py`, the expense routes in `app.py` |
| 4 Categories | `modules/categories.py`, `templates/categories.html` |
| 5 Budgets | `modules/budgets.py`, `templates/budgets.html` |
| 6 Transactions | `modules/transactions.py`, `modules/ledger.py`, `templates/transactions.html` |
| 7 Reports | `modules/reports.py`, `modules/charts.py`, `templates/reports.html`, `dashboard.html` |
| 8 Database and export | `database/`, `modules/exports.py` |
| 9 Interface | `templates/`, `static/style.css` |
| 10 Integration and testing | `app.py`, `tests/` |

## Requirements from the lecturer's brief

| Requirement | Where |
| --- | --- |
| Registration, login, logout | `authentication.py`, `/register`, `/login`, `/logout` |
| Record income and expenses | `income.py`, `expenses.py` |
| Categorise expenses | `categories.py`; the type rule is checked in code and by a database trigger |
| Balances | `reports.totals()`; the balance is calculated, never stored |
| Budgets and warnings | `budgets.py`; warning at 80% used, "over budget" above 100% |
| Monthly reports and charts | `/reports`, `reports.py`, `charts.py` |
| Search, edit, delete | `/transactions`, edit and delete pages with a confirmation step |
| CSV / Excel export | `/export/csv`, `/export/xlsx` (respects the active filters) |
| Database storage | SQLite, `schema.sql` |
| Automatic summaries | `reports.insights()` |

## Python concepts demonstrated (the brief asks for at least 8)

1. Functions and modules/packages: the `modules/` and `database/` packages
2. Classes and objects: `models.py`
3. Inheritance: `Income` and `Expense` extend `Transaction`
4. Polymorphism: `signed_amount()` is positive for income, negative for expenses
5. Encapsulation: `User` keeps its password hash private
6. Exception handling: custom errors in `errors.py`, SQLite errors converted in `db_connection.py`
7. Database programming: `sqlite3`, parameterised queries, transactions, triggers
8. Lists and dictionaries: report data, `KINDS` and `SORT_KEYS` tables
9. Sorting and filtering: `sorted()` with key functions; SQL filters
10. Input validation: `validators.py`
11. Authentication: hashed passwords, sessions, CSRF tokens
12. Unit testing: `unittest`, in `tests/`
13. File handling: CSV and Excel export
14. Data visualisation: matplotlib charts

## Security notes

- Passwords are stored as PBKDF2 hashes, never as plain text.
- Every query filters by the logged-in user's id. Another user's record gives a 404 page.
- All SQL uses bound parameters. Text search escapes `%` and `_`.
- Forms carry a CSRF token. Pages escape user text. Exported descriptions that start with `=`, `+`, `-` or `@` are prefixed so spreadsheets do not run them as formulas.
- The session secret is created once in `instance/secret_key`, or taken from the `SECRET_KEY` environment variable. `instance/` is in `.gitignore`.

## Decisions to mention in the presentation

- One currency (KES) and ISO dates (YYYY-MM-DD) everywhere.
- Description is optional. Amount, date and category are required.
- Income and expenses share one `transactions` table with a `transaction_type` column.
- The optional savings-goals table from the plan was left out to keep the core complete and tested.
- The app is single-user-per-account. Banking, mobile money and investment features are out of scope, as the plan says.

## Working as a group

Use one GitHub repository, one branch per member, and review before merging. Do not commit `instance/`, passwords, or real financial data.
