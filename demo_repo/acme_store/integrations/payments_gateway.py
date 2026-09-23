"""Adapter for the external payments provider.

The only external service this repo talks to. New integrations should follow
the same shape: read config from the environment, expose plain methods, and
return dictionaries rather than provider objects.
"""

import os
import uuid


class PaymentsGatewayError(RuntimeError):
    pass


class PaymentsGateway:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.environ.get("PAYMENTS_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "PAYMENTS_API_BASE", "https://api.payments.example.com"
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def charge(self, amount_cents: int, description: str = "") -> dict:
        if amount_cents <= 0:
            raise PaymentsGatewayError("amount must be positive")
        return {
            "reference": f"pay_{uuid.uuid4().hex[:12]}",
            "amount_cents": amount_cents,
            "description": description,
            "status": "captured",
        }

    def refund(self, provider_ref: str) -> dict:
        if not provider_ref:
            raise PaymentsGatewayError("provider_ref is required")
        return {
            "reference": provider_ref,
            "status": "refund_pending",
        }
