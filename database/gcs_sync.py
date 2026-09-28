"""Automatic Google Cloud Storage database persistence for Cloud Run."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import requests

import os
import sys

from config import settings

logger = logging.getLogger(__name__)

DB_BLOB_NAME = "tryout.db"


def is_gcs_sync_enabled() -> bool:
    """Return True only if a bucket is configured and not running tests."""
    bucket = getattr(settings, "gcs_db_bucket", "") or os.getenv("GCS_DB_BUCKET", "")
    if not bucket.strip():
        return False
    if os.getenv("TESTING") or "unittest" in sys.modules or "pytest" in sys.modules:
        return False
    return True


def get_gcs_bucket_name() -> str:
    return (getattr(settings, "gcs_db_bucket", "") or os.getenv("GCS_DB_BUCKET", "")).strip()


def _get_auth_token() -> str | None:
    """Obtain token via ADC or metadata server."""
    try:
        import google.auth
        from google.auth.transport.requests import Request

        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/devstorage.read_write"]
        )
        creds.refresh(Request())
        return creds.token
    except Exception as exc:
        logger.debug("Could not get Google auth token for GCS sync: %s", exc)
        return None


def restore_db_from_gcs() -> bool:
    """Download database from GCS on startup if it exists."""
    if not is_gcs_sync_enabled():
        return False

    bucket = get_gcs_bucket_name()
    token = _get_auth_token()
    if not token:
        return False

    db_path = settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    url = f"https://storage.googleapis.com/download/storage/v1/b/{bucket}/o/{DB_BLOB_NAME}?alt=media"
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 0:
            db_path.write_bytes(resp.content)
            logger.info(
                "Restored database from gs://%s/%s (%d bytes)",
                bucket,
                DB_BLOB_NAME,
                len(resp.content),
            )
            return True
        elif resp.status_code == 404:
            logger.info("No existing database found in gs://%s/%s. Starting fresh.", bucket, DB_BLOB_NAME)
        else:
            logger.warning("GCS restore returned status %s: %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.warning("Failed to restore database from GCS: %s", exc)
    return False


def backup_db_to_gcs_async() -> None:
    """Trigger an asynchronous background backup of SQLite database to GCS."""
    if not is_gcs_sync_enabled():
        return
    thread = threading.Thread(target=_backup_worker, daemon=True)
    thread.start()


def _backup_worker() -> None:
    if not is_gcs_sync_enabled():
        return

    bucket = get_gcs_bucket_name()
    token = _get_auth_token()
    if not token:
        return

    db_path = settings.database_path
    if not db_path.is_file():
        return

    try:
        data = db_path.read_bytes()
        if len(data) == 0:
            return
        url = f"https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o?uploadType=media&name={DB_BLOB_NAME}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
        }
        resp = requests.post(url, headers=headers, data=data, timeout=30)
        if resp.status_code in (200, 201):
            logger.info(
                "Successfully backed up database to gs://%s/%s (%d bytes)",
                bucket,
                DB_BLOB_NAME,
                len(data),
            )
        else:
            logger.warning("GCS backup upload failed with status %s: %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.warning("Error during GCS database backup: %s", exc)
