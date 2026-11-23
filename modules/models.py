"""Classes that represent the main things in the system.

Object-oriented ideas used here:
  * Encapsulation  - User keeps its password hash private (name-mangled).
  * Inheritance    - Income and Expense both inherit from Transaction.
  * Polymorphism   - signed_amount() and label behave differently per subclass.
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional

from werkzeug.security import check_password_hash

from modules.errors import ValidationError

# A budget shows a warning once spending reaches this share of the limit.
WARNING_THRESHOLD_PERCENT = 80


class User:
    def __init__(self, user_id, full_name, email, password_hash, created_at=None):
        self.user_id = user_id
        self.full_name = full_name
        self.email = email
        self.created_at = created_at
        self.__password_hash = password_hash  # private: never exposed or printed

    def check_password(self, password):
        return check_password_hash(self.__password_hash, password)

    @property
    def first_name(self):
        return self.full_name.split(" ")[0]

    def __repr__(self):
        return f"User(user_id={self.user_id}, email={self.email!r})"


class Transaction:
    """Base class for money moving in or out. Do not create it directly."""

    transaction_type = None
    label = "Transaction"

    def __init__(self, user_id, category_id, amount, transaction_date,
                 description="", transaction_id=None, category_name=None,
                 created_at=None):
        self.transaction_id = transaction_id
        self.user_id = user_id
        self.category_id = category_id
        self.amount = amount
        self.transaction_date = transaction_date
        self.description = description
        self.category_name = category_name
        self.created_at = created_at

    def signed_amount(self):
        """Effect on the balance: positive for income, negative for expenses."""
        raise NotImplementedError("Use Income or Expense")

    def validate(self):
        errors = {}
        if self.transaction_type not in ("income", "expense"):
            errors["type"] = "Transaction type must be income or expense."
        if not isinstance(self.amount, (int, float)) or self.amount <= 0:
            errors["amount"] = "Amount must be greater than zero."
        try:
            date.fromisoformat(self.transaction_date)
        except (TypeError, ValueError):
            errors["transaction_date"] = "Date must be in YYYY-MM-DD format."
        if errors:
            raise ValidationError(errors)

    def to_dict(self):
        return {
            "transaction_id": self.transaction_id,
            "type": self.transaction_type,
            "date": self.transaction_date,
            "category": self.category_name,
            "description": self.description,
            "amount": self.amount,
        }

    def __repr__(self):
        return (f"{type(self).__name__}(id={self.transaction_id}, "
                f"amount={self.amount}, date={self.transaction_date})")


class Income(Transaction):
    transaction_type = "income"
    label = "Income"

    def signed_amount(self):
        return self.amount


class Expense(Transaction):
    transaction_type = "expense"
    label = "Expense"

    def signed_amount(self):
        return -self.amount


TRANSACTION_CLASSES = {"income": Income, "expense": Expense}


def transaction_from_row(row):
    """Build the right subclass (Income or Expense) from a database row."""
    cls = TRANSACTION_CLASSES[row["transaction_type"]]
    return cls(
        user_id=row["user_id"],
        category_id=row["category_id"],
        amount=row["amount"],
        transaction_date=row["transaction_date"],
        description=row["description"],
        transaction_id=row["transaction_id"],
        category_name=row["category_name"],
        created_at=row["created_at"],
    )


@dataclass
class Category:
    category_id: int
    user_id: Optional[int]
    name: str
    category_type: str

    @property
    def is_default(self):
        return self.user_id is None


@dataclass
class Budget:
    budget_id: int
    user_id: int
    category_id: Optional[int]
    category_name: Optional[str]
    amount: float
    month: int
    year: int
    spent: float = 0.0

    @property
    def label(self):
        return self.category_name or "Overall monthly budget"

    @property
    def remaining(self):
        return round(self.amount - self.spent, 2)

    @property
    def overspent_by(self):
        return round(max(self.spent - self.amount, 0), 2)

    @property
    def percent_used(self):
        return round(self.spent / self.amount * 100, 1) if self.amount else 0.0

    @property
    def status(self):
        """'exceeded', 'warning' or 'ok'."""
        if self.spent > self.amount:
            return "exceeded"
        if self.percent_used >= WARNING_THRESHOLD_PERCENT:
            return "warning"
        return "ok"
