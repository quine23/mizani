"""Module 1: user registration, login and lookup.

Passwords are only ever stored as salted hashes. Login failures use one
generic message so an attacker cannot tell which emails are registered.
"""
from werkzeug.security import check_password_hash, generate_password_hash

from database import db_connection as db
from modules.errors import AuthenticationError, IntegrityViolation, NotFoundError, ValidationError
from modules.models import User
from modules.validators import Validator, clean_email, clean_full_name, clean_password

HASH_METHOD = "pbkdf2:sha256"
# Checked when the email is unknown so login takes similar time either way.
_DUMMY_HASH = generate_password_hash("not-a-real-password", method=HASH_METHOD)


def _row_to_user(row):
    return User(row["user_id"], row["full_name"], row["email"],
                row["password_hash"], row["created_at"])


def register_user(full_name, email, password, confirm_password):
    v = Validator()
    full_name = v.check("full_name", clean_full_name, full_name)
    email = v.check("email", clean_email, email)
    password = v.check("password", clean_password, password)
    if password is not None and password != str(confirm_password or ""):
        v.errors["confirm_password"] = "Passwords do not match."
    v.raise_if_invalid()

    if db.query_one("SELECT 1 FROM users WHERE email = ?", (email,)):
        raise ValidationError({"email": "An account with this email already exists."})

    try:
        result = db.execute(
            "INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)",
            (full_name, email, generate_password_hash(password, method=HASH_METHOD)),
        )
    except IntegrityViolation:
        raise ValidationError({"email": "An account with this email already exists."}) from None
    return get_user(result.lastrowid)


def login_user(email, password):
    email = str(email or "").strip().lower()
    row = db.query_one("SELECT * FROM users WHERE email = ?", (email,))
    if row is None:
        check_password_hash(_DUMMY_HASH, str(password or ""))
        raise AuthenticationError("Invalid email or password.")
    user = _row_to_user(row)
    if not user.check_password(str(password or "")):
        raise AuthenticationError("Invalid email or password.")
    return user


def get_user(user_id):
    row = db.query_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if row is None:
        raise NotFoundError("User not found.")
    return _row_to_user(row)
