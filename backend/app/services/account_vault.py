"""Encrypted storage for the account facts Orion needs to pass verification.

A real retention line asks who you are before it will discuss the account:
account number, the name on it, the service address, often a security PIN or
the last four of an SSN. Orion cannot negotiate past that question without the
answers, so the account holder supplies them once when they sign the
authorisation.

These are the most sensitive fields the product touches, so:
  - they are encrypted at rest with Fernet and never stored in plaintext,
  - they are never logged, never returned by the read APIs, and never placed in
    the agent's system prompt - the agent has to call a tool for each field,
    which also leaves an audit trail of exactly what was disclosed on a call,
  - a missing ACCOUNT_ENCRYPTION_KEY is a hard failure, not a silent fallback
    to storing them in the clear.
"""

import json
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)

# What a rep can ask for, and nothing else. Anything outside this list is
# refused by provide_verification below rather than guessed at.
DISCLOSABLE_FIELDS = (
    "account_holder_name",
    "account_number",
    "service_address",
    "billing_zip",
    "security_pin",
    "last4_ssn",
    "date_of_birth",
)

# Human-readable, for telling the agent what it can answer without ever
# putting the values themselves in the prompt.
FIELD_LABELS = {
    "account_holder_name": "the name on the account",
    "account_number": "the account number",
    "service_address": "the service address",
    "billing_zip": "the billing ZIP code",
    "security_pin": "the account security PIN",
    "last4_ssn": "the last four digits of the account holder's SSN",
    "date_of_birth": "the account holder's date of birth",
}


class VaultNotConfigured(RuntimeError):
    pass


@lru_cache
def _cipher() -> Fernet:
    if not settings.account_encryption_key:
        raise VaultNotConfigured(
            "ACCOUNT_ENCRYPTION_KEY is not set - generate one with "
            "`python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"`"
        )
    return Fernet(settings.account_encryption_key.encode())


def seal(details: dict[str, str]) -> str:
    """Encrypt the supplied fields into a single opaque string."""
    cleaned = {
        key: str(value).strip()
        for key, value in details.items()
        if key in DISCLOSABLE_FIELDS and str(value).strip()
    }
    return _cipher().encrypt(json.dumps(cleaned).encode()).decode()


def unseal(blob: str | None) -> dict[str, str]:
    """Decrypt, returning {} for anything unreadable.

    A key rotation makes old blobs undecryptable; that must degrade to "Orion
    can't answer verification" rather than crashing a live call.
    """
    if not blob:
        return {}
    try:
        return json.loads(_cipher().decrypt(blob.encode()).decode())
    except (InvalidToken, ValueError):
        logger.warning("Stored account details could not be decrypted")
        return {}


def available_fields(blob: str | None) -> list[str]:
    """Which fields are on file - names only, never values."""
    return [field for field in DISCLOSABLE_FIELDS if field in unseal(blob)]
