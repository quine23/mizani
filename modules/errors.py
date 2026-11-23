"""Custom exceptions shared by every module.

Using our own exception types lets the web layer decide what to show the user
without having to know how each module works internally.
"""


class FinanceError(Exception):
    """Base class for all application errors."""


class ValidationError(FinanceError):
    """One or more inputs were rejected. `errors` maps field name -> message."""

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = {"form": errors}
        self.errors = dict(errors)
        super().__init__("; ".join(self.errors.values()))


class AuthenticationError(FinanceError):
    """Login failed or the user is not allowed to continue."""


class NotFoundError(FinanceError):
    """A record does not exist, or belongs to a different user."""


class DatabaseError(FinanceError):
    """The database could not complete an operation."""


class IntegrityViolation(DatabaseError):
    """A database rule (UNIQUE, CHECK, FOREIGN KEY) was broken."""
