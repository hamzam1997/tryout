"""In-memory data store.

Stands in for a database so the app runs with no external setup.
"""

from datetime import datetime, timedelta, timezone

from models import Order, Payment, User

users: dict[int, User] = {}
orders: dict[int, Order] = {}
payments: dict[int, Payment] = {}

_next_id = {"order": 1, "payment": 1}


def next_id(kind: str) -> int:
    value = _next_id[kind]
    _next_id[kind] = value + 1
    return value


def reset() -> None:
    """Restore the seeded fixtures. Called on startup and between tests."""
    users.clear()
    orders.clear()
    payments.clear()
    _next_id.update({"order": 1, "payment": 1})

    now = datetime.now(timezone.utc)

    for user in (
        User(id=1, name="Dana Whitfield", email="dana@example.com"),
        User(id=2, name="Marco Reyes", email="marco@example.com"),
        User(id=3, name="Priya Raman", email="priya@example.com"),
    ):
        users[user.id] = user

    seeds = [
        # user, cents, order status, payment status, refund requested days ago
        (1, 4200, "delivered", "captured", None),
        (2, 15900, "delivered", "refund_requested", 9),
        (3, 8350, "delivered", "refund_requested", 4),
        (1, 2999, "delivered", "refunded", 12),
        (2, 6100, "placed", "captured", None),
    ]

    for user_id, cents, order_status, payment_status, requested_days_ago in seeds:
        order = Order(
            id=next_id("order"),
            user_id=user_id,
            total_cents=cents,
            status=order_status,
            created_at=now - timedelta(days=20),
        )
        orders[order.id] = order

        requested_at = (
            now - timedelta(days=requested_days_ago)
            if requested_days_ago is not None
            else None
        )
        payment = Payment(
            id=next_id("payment"),
            order_id=order.id,
            amount_cents=cents,
            status=payment_status,
            provider_ref=f"pay_{order.id:06d}",
            refund_requested_at=requested_at,
            refunded_at=(
                now - timedelta(days=10) if payment_status == "refunded" else None
            ),
            created_at=now - timedelta(days=20),
        )
        payments[payment.id] = payment


def payment_for_order(order_id: int) -> Payment | None:
    for payment in payments.values():
        if payment.order_id == order_id:
            return payment
    return None


reset()
