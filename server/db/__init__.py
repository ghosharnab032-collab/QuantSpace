"""Database package exports."""

from .database import (
    check_db_connection,
    close_db_client,
    get_db_client,
    init_db,
)
from .crud import (
    create_user,
    get_user_by_email,
    get_user_by_id,
)
from .entitlements import (
    grant_entitlement,
    get_entitlement,
    revoke_entitlement,
)
from .payments import (
    create_payment,
    get_payment_by_order_id,
    get_payment_by_payment_id,
    get_verified_payment,
    mark_payment_verified,
)

__all__ = [
    # Database
    "get_db_client",
    "close_db_client",
    "init_db",
    "check_db_connection",

    # Users
    "create_user",
    "get_user_by_email",
    "get_user_by_id",

    # Entitlements
    "grant_entitlement",
    "get_entitlement",
    "revoke_entitlement",
    "create_payment",
    "get_payment_by_order_id",
    "get_payment_by_payment_id",
    "get_verified_payment",
    "mark_payment_verified",
]