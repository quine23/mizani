-- Mizani: Personal Finance and Expense Management System
-- Shared schema used by every module. Amounts are in one currency (KES) and
-- dates are stored as ISO text (YYYY-MM-DD).
-- A balance is never stored; it is always calculated from transactions.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- user_id IS NULL means a default category visible to everyone.
CREATE TABLE IF NOT EXISTS categories (
    category_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    category_name TEXT NOT NULL,
    category_type TEXT NOT NULL CHECK (category_type IN ('income', 'expense')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_categories_default
    ON categories (category_name COLLATE NOCASE, category_type)
    WHERE user_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_categories_user
    ON categories (user_id, category_name COLLATE NOCASE, category_type)
    WHERE user_id IS NOT NULL;

-- Income and expenses live in one table, told apart by transaction_type.
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    category_id      INTEGER NOT NULL REFERENCES categories(category_id) ON DELETE RESTRICT,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('income', 'expense')),
    amount           REAL NOT NULL CHECK (amount > 0),
    description      TEXT NOT NULL DEFAULT '',
    transaction_date TEXT NOT NULL
        CHECK (transaction_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_transactions_user_date
    ON transactions (user_id, transaction_date);
CREATE INDEX IF NOT EXISTS ix_transactions_user_category
    ON transactions (user_id, category_id);

-- Safety net: even if application code is bypassed, the database refuses a
-- category of the wrong type, or one that belongs to another user.
CREATE TRIGGER IF NOT EXISTS trg_transactions_category_insert
BEFORE INSERT ON transactions
BEGIN
    SELECT RAISE(ABORT, 'Category does not match the transaction type or belongs to another user')
    WHERE NOT EXISTS (
        SELECT 1 FROM categories c
        WHERE c.category_id = NEW.category_id
          AND c.category_type = NEW.transaction_type
          AND (c.user_id IS NULL OR c.user_id = NEW.user_id)
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_transactions_category_update
BEFORE UPDATE ON transactions
BEGIN
    SELECT RAISE(ABORT, 'Category does not match the transaction type or belongs to another user')
    WHERE NOT EXISTS (
        SELECT 1 FROM categories c
        WHERE c.category_id = NEW.category_id
          AND c.category_type = NEW.transaction_type
          AND (c.user_id IS NULL OR c.user_id = NEW.user_id)
    );
END;

-- category_id NULL means the overall monthly budget.
CREATE TABLE IF NOT EXISTS budgets (
    budget_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    category_id   INTEGER REFERENCES categories(category_id) ON DELETE RESTRICT,
    budget_amount REAL NOT NULL CHECK (budget_amount > 0),
    month         INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    year          INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2100),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_budgets_category
    ON budgets (user_id, category_id, month, year)
    WHERE category_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_budgets_overall
    ON budgets (user_id, month, year)
    WHERE category_id IS NULL;
