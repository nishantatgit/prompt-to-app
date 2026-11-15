"""Edit keys: proof that a change request comes from whoever built the app.

Vyskar has no logins. When a new app is built, the browser gets a random
edit key, and the app's Vercel project keeps only its SHA-256 hash. A change
to the app is accepted only with a key whose hash matches. The key is 256
random bits, so a plain hash is enough: there is nothing to guess.
"""

import hashlib
import hmac
import secrets

ENV_KEY = "VYSKAR_EDIT_KEY_HASH"


def new_key() -> str:
    return secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def matches(key: str, stored_hash: str | None) -> bool:
    return bool(stored_hash) and hmac.compare_digest(hash_key(key), stored_hash)
