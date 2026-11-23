"""Fill the database with a demo user and three months of sample records.

Usage:  python seed_demo.py
Then log in with  demo@example.com  /  Demo1234
"""
from datetime import date

from database import db_connection as db
from modules import authentication, budgets, categories, expenses, income
from modules.errors import ValidationError

DEMO_EMAIL, DEMO_PASSWORD = "demo@example.com", "Demo1234"


def category_id(user_id, name, kind):
    for c in categories.list_categories(user_id, kind):
        if c.name == name:
            return c.category_id
    return categories.add_category(user_id, name, kind).category_id


def month_back(today, back):
    total = today.year * 12 + today.month - 1 - back
    return total // 12, total % 12 + 1


def main():
    db.init_db()
    try:
        user = authentication.register_user("Demo Student", DEMO_EMAIL, DEMO_PASSWORD, DEMO_PASSWORD)
    except ValidationError:
        print("Demo user already exists. Nothing to do.")
        return
    uid = user.user_id
    today = date.today()
    spending = [  # (day, category, amount, note)
        (2, "Rent", 8500, "Hostel rent"), (4, "Food", 1200, "Groceries"),
        (7, "Transport", 450, "Matatu fare"), (9, "Airtime and data", 500, "Data bundle"),
        (12, "Food", 950, "Cafeteria"), (15, "Education", 1800, "Printing and books"),
        (18, "Entertainment", 700, "Movie night"), (21, "Food", 1100, "Groceries"),
        (24, "Health", 600, "Pharmacy"), (27, "Shopping", 1300, "Shoes"),
    ]
    for back in (2, 1, 0):
        year, month = month_back(today, back)
        income.add_income(uid, 15000, date(year, month, 1).isoformat(),
                          category_id(uid, "Allowance", "income"), "Monthly allowance")
        income.add_income(uid, 6000 + back * 500, date(year, month, 10).isoformat(),
                          category_id(uid, "Business", "income"), "Freelance web work")
        for day, name, amount, note in spending:
            if back == 0 and day > today.day:
                continue
            factor = 1 + (2 - back) * 0.04
            expenses.add_expense(uid, round(amount * factor, 2), date(year, month, day).isoformat(),
                                 category_id(uid, name, "expense"), note)
        budgets.set_budget(uid, 18000, month, year)
        budgets.set_budget(uid, 5000, month, year, category_id(uid, "Food", "expense"))
    print(f"Demo data created. Log in with {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
