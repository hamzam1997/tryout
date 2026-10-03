"""Firestore connection management and client initialization.

Supports:
1. Live Google Cloud Firestore (using Application Default Credentials or GOOGLE_CLOUD_PROJECT).
2. Firestore Emulator (when FIRESTORE_EMULATOR_HOST is set).
3. In-memory Mock Firestore Store for offline local testing and unit tests.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

_firestore_client: Any = None
_client_lock = threading.Lock()
_use_memory_fallback = False


class InMemoryDocumentReference:
    def __init__(self, doc_id: str, collection: InMemoryCollectionReference):
        self.id = doc_id
        self._collection = collection

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        self._collection._set_doc(self.id, data, merge=merge)

    def get(self) -> InMemoryDocumentSnapshot:
        data = self._collection._get_doc(self.id)
        return InMemoryDocumentSnapshot(self.id, data)

    def delete(self) -> None:
        self._collection._delete_doc(self.id)


class InMemoryDocumentSnapshot:
    def __init__(self, doc_id: str, data: dict[str, Any] | None):
        self.id = doc_id
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return dict(self._data) if self._data is not None else None


class InMemoryQuery:
    def __init__(self, collection: InMemoryCollectionReference, filters=None, order_field=None, descending=False):
        self._collection = collection
        self._filters = filters or []
        self._order_field = order_field
        self._descending = descending

    def where(self, field: str, op: str, value: Any) -> InMemoryQuery:
        new_filters = list(self._filters)
        new_filters.append((field, op, value))
        return InMemoryQuery(self._collection, new_filters, self._order_field, self._descending)

    def order_by(self, field: str, direction=None) -> InMemoryQuery:
        from google.cloud.firestore import Query
        desc = (direction == Query.DESCENDING or direction == "DESCENDING")
        return InMemoryQuery(self._collection, self._filters, field, desc)

    def stream(self):
        docs = []
        for doc_id, data in self._collection._data.items():
            matches = True
            for field, op, val in self._filters:
                doc_val = data.get(field)
                if op in ("==", "="):
                    if doc_val != val:
                        matches = False
                        break
                elif op == "!=":
                    if doc_val == val:
                        matches = False
                        break
            if matches:
                docs.append(InMemoryDocumentSnapshot(doc_id, data))

        if self._order_field:
            def sort_key(s):
                val = (s.to_dict() or {}).get(self._order_field)
                return str(val) if val is not None else ""
            docs.sort(key=sort_key, reverse=self._descending)

        return docs


class InMemoryCollectionReference:
    def __init__(self, name: str, client: InMemoryFirestoreClient):
        self.name = name
        self._client = client
        self._data: dict[str, dict[str, Any]] = {}

    def document(self, doc_id: str) -> InMemoryDocumentReference:
        return InMemoryDocumentReference(str(doc_id), self)

    def _set_doc(self, doc_id: str, data: dict[str, Any], merge: bool = False) -> None:
        if merge and doc_id in self._data:
            self._data[doc_id].update(data)
        else:
            self._data[doc_id] = dict(data)

    def _get_doc(self, doc_id: str) -> dict[str, Any] | None:
        return self._data.get(doc_id)

    def _delete_doc(self, doc_id: str) -> None:
        self._data.pop(doc_id, None)

    def where(self, field: str, op: str, value: Any) -> InMemoryQuery:
        return InMemoryQuery(self).where(field, op, value)

    def order_by(self, field: str, direction=None) -> InMemoryQuery:
        return InMemoryQuery(self).order_by(field, direction)

    def stream(self):
        return [InMemoryDocumentSnapshot(k, v) for k, v in self._data.items()]


class InMemoryFirestoreClient:
    def __init__(self):
        self._collections: dict[str, InMemoryCollectionReference] = {}
        self._counters: dict[str, int] = {}
        self._lock = threading.Lock()

    def collection(self, name: str) -> InMemoryCollectionReference:
        with self._lock:
            if name not in self._collections:
                self._collections[name] = InMemoryCollectionReference(name, self)
            return self._collections[name]

    def next_id(self, counter_name: str) -> int:
        with self._lock:
            val = self._counters.get(counter_name, 0) + 1
            self._counters[counter_name] = val
            return val

    def clear(self) -> None:
        with self._lock:
            self._collections.clear()
            self._counters.clear()


_mock_client = InMemoryFirestoreClient()


def force_in_memory_firestore(enabled: bool = True) -> None:
    """Explicitly use in-memory store (primarily for unit tests)."""
    global _use_memory_fallback
    _use_memory_fallback = enabled
    if enabled:
        _mock_client.clear()


def reset_in_memory_firestore() -> None:
    """Clear in-memory store between tests."""
    _mock_client.clear()


def get_firestore_client():
    """Return the Firestore client, using in-memory store if offline/unconfigured."""
    global _firestore_client, _use_memory_fallback

    if _use_memory_fallback:
        return _mock_client

    if _firestore_client is not None:
        return _firestore_client

    with _client_lock:
        if _firestore_client is not None:
            return _firestore_client

        try:
            from google.cloud import firestore

            project = (
                settings.google_cloud_project
                or os.environ.get("GOOGLE_CLOUD_PROJECT")
                or None
            )
            database = (
                settings.firestore_database
                if settings.firestore_database != "(default)"
                else None
            )

            if database:
                client = firestore.Client(project=project, database=database)
            elif project:
                client = firestore.Client(project=project)
            else:
                client = firestore.Client()

            # Probe connectivity to ensure Firestore API is enabled in this project
            client.collection("counters").document("probe").get(timeout=3)
            logger.info("Initialized and verified Google Cloud Firestore client for project %s", client.project)
            _firestore_client = client
            return _firestore_client
        except Exception as exc:
            logger.warning(
                "Google Cloud Firestore is disabled or unreachable (%s). "
                "Falling back to in-memory storage so all endpoints continue working locally.",
                exc,
            )
            _use_memory_fallback = True
            return _mock_client


def get_next_id(entity_name: str) -> int:
    """Generate a monotonic integer ID for an entity using Firestore."""
    client = get_firestore_client()

    if isinstance(client, InMemoryFirestoreClient):
        return client.next_id(entity_name)

    # Live Cloud Firestore: use atomic increment on a counter doc
    from google.cloud import firestore

    counter_ref = client.collection("counters").document("entities")
    try:
        # Atomic increment transaction
        @firestore.transactional
        def _increment_in_transaction(transaction, ref):
            snapshot = ref.get(transaction=transaction)
            current = 0
            if snapshot.exists:
                current = snapshot.to_dict().get(entity_name, 0)
            next_val = current + 1
            transaction.set(ref, {entity_name: next_val}, merge=True)
            return next_val

        transaction = client.transaction()
        return _increment_in_transaction(transaction, counter_ref)
    except Exception as exc:
        logger.warning("Failed transactional counter, using document count fallback: %s", exc)
        # Fallback: count documents in collection
        return len(list(client.collection(entity_name).stream())) + 1
