from flask import Blueprint, jsonify, request

import store
from integrations.payments_gateway import PaymentsGateway, PaymentsGatewayError
from models import Order, Payment

bp = Blueprint("checkout", __name__)


@bp.route("/checkout", methods=["POST"])
def checkout():
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    total_cents = body.get("total_cents")

    if user_id not in store.users:
        return jsonify({"error": "unknown user"}), 400
    if not isinstance(total_cents, int) or total_cents <= 0:
        return jsonify({"error": "total_cents must be a positive integer"}), 400

    order = Order(id=store.next_id("order"), user_id=user_id, total_cents=total_cents)
    store.orders[order.id] = order

    gateway = PaymentsGateway()
    try:
        charge = gateway.charge(total_cents, description=f"order {order.id}")
    except PaymentsGatewayError as exc:
        return jsonify({"error": str(exc)}), 502

    payment = Payment(
        id=store.next_id("payment"),
        order_id=order.id,
        amount_cents=total_cents,
        status=charge["status"],
        provider_ref=charge["reference"],
    )
    store.payments[payment.id] = payment

    return jsonify({"order": order.to_dict(), "payment": payment.to_dict()}), 201
