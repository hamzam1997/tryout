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
import time
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


class _GCloudCredentials:
    """Wrapper that provides an active OAuth2 token from the gcloud CLI when ADC lacks Firestore permissions."""
    def __init__(self):
        self.token = None

    def refresh(self, request):
        import subprocess
        try:
            self.token = subprocess.check_output(
                ["gcloud", "auth", "print-access-token"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except Exception as exc:
            logger.warning("Failed to refresh token from gcloud CLI: %s", exc)

    def apply(self, headers):
        if not self.token:
            self.refresh(None)
        headers["authorization"] = f"Bearer {self.token}"

    def before_request(self, request, method, url, headers):
        self.apply(headers)


def _get_live_credentials(project: str | None = None):
    """Obtain credentials for Firestore, preferring ADC and falling back to gcloud user credentials."""
    import google.auth
    from google.auth.transport.requests import Request
    from google.cloud import firestore

    try:
        creds, _ = google.auth.default()
        creds.refresh(Request())
        # Smoke test ADC against Firestore to verify it has permissions
        test_client = firestore.Client(project=project, credentials=creds)
        list(test_client.collection("repositories").limit(1).get())
        return creds
    except Exception as exc:
        logger.info("ADC credentials did not have Firestore permission (%s); trying gcloud CLI credentials...", exc)

    try:
        from google.auth.credentials import Credentials

        class GCloudUserCredentials(Credentials):
            def __init__(self):
                super().__init__()
                self.token = None

            def refresh(self, request):
                import subprocess
                self.token = subprocess.check_output(
                    ["gcloud", "auth", "print-access-token"],
                    stderr=subprocess.DEVNULL
                ).decode().strip()

        creds = GCloudUserCredentials()
        creds.refresh(None)
        test_client = firestore.Client(project=project, credentials=creds)
        list(test_client.collection("repositories").limit(1).get())
        logger.info("Using active gcloud CLI account credentials for Firestore.")
        return creds
    except Exception as exc:
        logger.warning("Could not obtain gcloud CLI credentials: %s", exc)
        return None


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

            creds = _get_live_credentials(project=project)

            kwargs = {}
            if project:
                kwargs["project"] = project
            if database:
                kwargs["database"] = database
            if creds:
                kwargs["credentials"] = creds

            client = firestore.Client(**kwargs)

            logger.info("Initialized Google Cloud Firestore client for project %s", client.project)
            _firestore_client = client
            return _firestore_client
        except Exception as exc:
            logger.warning(
                "Could not connect to Google Cloud Firestore (%s). Falling back to in-memory Firestore.",
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
    except Exception:
        # A "count + 1" fallback hands concurrent writers the same id and overwrites docs.
        logger.exception("Could not allocate a %s id", entity_name)
        raise


LOCK_TTL_SECONDS = 120


def claim(key: str) -> bool:
    """Take a cross-process lock; False if someone else holds it. Pair with release().
    A holder that died is ignored after LOCK_TTL_SECONDS."""
    # ponytail: TTL lock, not a lease; a holder slower than the TTL can overlap the next one.
    client = get_firestore_client()
    now = time.time()
    if isinstance(client, InMemoryFirestoreClient):
        with client._lock:
            locks = client._collections.setdefault("locks", InMemoryCollectionReference("locks", client))
            held = locks._get_doc(key)
            if held and now - held["at"] < LOCK_TTL_SECONDS:
                return False
            locks._set_doc(key, {"at": now})
            return True

    from google.api_core.exceptions import AlreadyExists

    ref = client.collection("locks").document(key)
    try:
        ref.create({"at": now})
        return True
    except AlreadyExists:
        snap = ref.get()
        if snap.exists and now - snap.to_dict().get("at", 0) < LOCK_TTL_SECONDS:
            return False
        ref.delete()
        try:
            ref.create({"at": now})
            return True
        except AlreadyExists:
            return False


def release(key: str) -> None:
    get_firestore_client().collection("locks").document(key).delete()
