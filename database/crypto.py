"""Encrypt credentials stored in Firestore (workspace GitHub tokens)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from config import settings


def _fernet() -> Fernet:
    # ponytail: key derived from SECRET_KEY, so rotating it disconnects stored tokens;
    # move to Secret Manager / KMS envelope keys when there are real customer tokens.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest()))


def encrypt(text: str) -> str:
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
