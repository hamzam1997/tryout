# Acme Store

The order and payment service for Acme, a small online retailer. Flask, no
database — orders and payments live in an in-memory store seeded at startup.

Used as the pre-loaded demo repository for tryout.

## Running

```bash
pip install -r requirements.txt
python app.py
```

## Tests

```bash
python -m unittest discover -s tests
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service check |
| GET | `/orders` | All orders |
| GET | `/orders/<id>` | One order with its payment |
| POST | `/checkout` | Create an order and charge it |
| GET | `/refunds` | Payments awaiting or completing a refund |
| POST | `/refunds` | Request a refund for an order |

## Layout

```
app.py                             Flask app factory
models.py                          User, Order, Payment
store.py                           In-memory store and seed fixtures
integrations/payments_gateway.py   The external payments provider
routes/                            Blueprints
tests/                             Baseline suite
```

## Known gaps

Things the team knows are missing. They are listed here rather than tracked,
which is itself part of the problem.

- **No reason recorded for refund delays.** `Payment.refund_requested_at` tells
  us a refund is outstanding, but nothing records *why* it is taking time —
  provider hold, manual review, or a failed callback all look identical.
- **No customer messaging from this service.** Anything customer-facing goes
  through notifications-service, owned by @team-comms. There is no client for
  it here and no credentials in `.env.example`.
- **No refund SLA.** Nobody has decided how many days makes a refund "delayed",
  so support answers case by case.
