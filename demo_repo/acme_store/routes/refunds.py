from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

import store
from integrations.payments_gateway import PaymentsGateway, PaymentsGatewayError

bp = Blueprint("refunds", __name__)


@bp.route("/refunds")
def list_refunds():
    """Every payment currently awaiting or completing a refund."""
    pending = [
        payment.to_dict()
        for payment in store.payments.values()
        if payment.status in ("refund_requested", "refunded")
    ]
    return jsonify(pending)


@bp.route("/refunds", methods=["POST"])
def request_refund():
    body = request.get_json(silent=True) or {}
    order_id = body.get("order_id")

    payment = store.payment_for_order(order_id) if order_id else None
    if payment is None:
        return jsonify({"error": "no payment for that order"}), 404
    if payment.status != "captured":
        return jsonify({"error": f"payment is {payment.status}"}), 409

    gateway = PaymentsGateway()
    try:
        gateway.refund(payment.provider_ref)
    except PaymentsGatewayError as exc:
        return jsonify({"error": str(exc)}), 502

    payment.status = "refund_requested"
    payment.refund_requested_at = datetime.now(timezone.utc)

    return jsonify(payment.to_dict()), 202
