"""Raw SQL schema definitions."""

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);
"""


CREATE_EMAIL_INDEX = """
CREATE INDEX IF NOT EXISTS idx_users_email
ON users(email);
"""


CREATE_ENTITLEMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS entitlements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    feature TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    expires_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    UNIQUE(user_id, feature)
);
"""


CREATE_ENTITLEMENTS_USER_INDEX = """
CREATE INDEX IF NOT EXISTS idx_entitlements_user_id
ON entitlements(user_id);
"""


# ------------------------------------------------------------------
# Payments
# ------------------------------------------------------------------

CREATE_PAYMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,

    product TEXT NOT NULL,

    amount INTEGER NOT NULL,

    currency TEXT NOT NULL DEFAULT 'INR',

    razorpay_order_id TEXT NOT NULL UNIQUE,

    razorpay_payment_id TEXT UNIQUE,

    status TEXT NOT NULL DEFAULT 'created',

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    verified_at DATETIME,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);
"""


CREATE_PAYMENTS_USER_INDEX = """
CREATE INDEX IF NOT EXISTS idx_payments_user_id
ON payments(user_id);
"""


CREATE_PAYMENTS_STATUS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_payments_status
ON payments(status);
"""


SCHEMA_STATEMENTS = [
    CREATE_USERS_TABLE,
    CREATE_EMAIL_INDEX,
    CREATE_ENTITLEMENTS_TABLE,
    CREATE_ENTITLEMENTS_USER_INDEX,
    CREATE_PAYMENTS_TABLE,
    CREATE_PAYMENTS_USER_INDEX,
    CREATE_PAYMENTS_STATUS_INDEX,
]