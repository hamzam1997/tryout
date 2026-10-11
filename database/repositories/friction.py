"""Friction log persistence layer using Cloud Firestore."""

from __future__ import annotations

from collections import Counter
from database.client import get_firestore_client, get_next_id
from database.scope import exists, scoped, stamped
from database.documents import FrictionLogDoc
from schemas import FrictionLog

ALLOWED_COLUMNS = {"category", "service_name", "owning_team"}


def create_friction_log(log: FrictionLog) -> FrictionLog:
    client = get_firestore_client()
    log_id = log.id or get_next_id("friction_logs")
    log.id = log_id

    doc = FrictionLogDoc.from_domain(log)
    client.collection(FrictionLogDoc.COLLECTION).document(str(log_id)).set(stamped(doc.to_doc()))
    return log


def list_friction_logs(attempt_id: int | None = None) -> list[FrictionLog]:
    client = get_firestore_client()
    query = scoped(client.collection(FrictionLogDoc.COLLECTION))
    if attempt_id is not None:
        query = query.where("attempt_id", "==", attempt_id)

    docs = query.stream()
    logs = []
    for d in docs:
        data = d.to_dict()
        if data:
            logs.append(FrictionLogDoc.from_doc(data).to_domain())
    logs.sort(key=lambda x: x.id)
    return logs


def count_friction_by(column: str) -> list[tuple[str, int]]:
    """Aggregate friction logs for the bottleneck map."""
    if column not in ALLOWED_COLUMNS:
        raise ValueError(f"cannot group friction logs by {column!r}")

    client = get_firestore_client()
    docs = scoped(client.collection(FrictionLogDoc.COLLECTION)).stream()

    counter: Counter[str] = Counter()
    for d in docs:
        data = d.to_dict() or {}
        val = data.get(column)
        if val:
            counter[str(val)] += 1

    # Sort by total descending, then key ascending
    sorted_items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return sorted_items
