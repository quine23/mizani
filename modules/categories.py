"""Module 4: default and custom categories.

Default categories (user_id NULL) are shared and read-only. Custom categories
belong to one user and can never be seen or used by another user.
"""
from database import db_connection as db
from modules.errors import IntegrityViolation, NotFoundError, ValidationError
from modules.models import Category
from modules.validators import Validator, clean_category_name, clean_type


def _from_row(row):
    return Category(row["category_id"], row["user_id"], row["category_name"], row["category_type"])


def list_categories(user_id, category_type=None):
    """Default categories first, then this user's own, grouped by type."""
    sql = "SELECT * FROM categories WHERE (user_id IS NULL OR user_id = ?)"
    params = [user_id]
    if category_type is not None:
        sql += " AND category_type = ?"
        params.append(clean_type(category_type))
    sql += (" ORDER BY category_type, user_id IS NOT NULL, "
            "CASE WHEN user_id IS NULL THEN category_id ELSE 0 END, category_name COLLATE NOCASE")
    return [_from_row(row) for row in db.query_all(sql, params)]


def get_category(user_id, category_id):
    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        raise NotFoundError("Category not found.") from None
    row = db.query_one(
        "SELECT * FROM categories WHERE category_id = ? AND (user_id IS NULL OR user_id = ?)",
        (category_id, user_id),
    )
    if row is None:
        raise NotFoundError("Category not found.")
    return _from_row(row)


def _name_taken(user_id, name, category_type, ignore_id=None):
    row = db.query_one(
        "SELECT 1 FROM categories WHERE (user_id IS NULL OR user_id = ?) "
        "AND lower(category_name) = lower(?) AND category_type = ? AND category_id != ?",
        (user_id, name, category_type, ignore_id or -1),
    )
    return row is not None


def add_category(user_id, name, category_type):
    v = Validator()
    name = v.check("name", clean_category_name, name)
    category_type = v.check("category_type", clean_type, category_type)
    v.raise_if_invalid()
    if _name_taken(user_id, name, category_type):
        raise ValidationError({"name": f"You already have an {category_type} category called '{name}'."})
    try:
        result = db.execute(
            "INSERT INTO categories (user_id, category_name, category_type) VALUES (?, ?, ?)",
            (user_id, name, category_type),
        )
    except IntegrityViolation:
        raise ValidationError({"name": f"You already have an {category_type} category called '{name}'."}) from None
    return get_category(user_id, result.lastrowid)


def rename_category(user_id, category_id, new_name):
    category = get_category(user_id, category_id)
    if category.is_default:
        raise ValidationError({"name": "Default categories cannot be renamed."})
    v = Validator()
    new_name = v.check("name", clean_category_name, new_name)
    v.raise_if_invalid()
    if _name_taken(user_id, new_name, category.category_type, ignore_id=category.category_id):
        raise ValidationError({"name": f"You already have an {category.category_type} category called '{new_name}'."})
    db.execute("UPDATE categories SET category_name = ? WHERE category_id = ? AND user_id = ?",
               (new_name, category.category_id, user_id))
    return get_category(user_id, category.category_id)


def delete_category(user_id, category_id):
    category = get_category(user_id, category_id)
    if category.is_default:
        raise ValidationError({"category": "Default categories cannot be deleted."})
    used_by_txn = db.query_one(
        "SELECT COUNT(*) AS n FROM transactions WHERE category_id = ? AND user_id = ?",
        (category.category_id, user_id))["n"]
    used_by_budget = db.query_one(
        "SELECT COUNT(*) AS n FROM budgets WHERE category_id = ? AND user_id = ?",
        (category.category_id, user_id))["n"]
    if used_by_txn or used_by_budget:
        raise ValidationError({
            "category": f"'{category.name}' is used by {used_by_txn} transaction(s) and "
                        f"{used_by_budget} budget(s). Move or delete those first."})
    db.execute("DELETE FROM categories WHERE category_id = ? AND user_id = ?",
               (category.category_id, user_id))
    return category
