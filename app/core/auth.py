import time
import uuid
from threading import Lock
from app.core.config import OAUTH

# In-memory token store: token -> (client_id, expires_at)
_TOKENS = {}
_LOCK = Lock()


def issue_token(client_id: str, client_secret: str):
    clients = OAUTH.get("clients", {})
    expected = clients.get(client_id)
    if expected is None or expected != client_secret:
        return None

    token = str(uuid.uuid4())
    ttl = OAUTH.get("token_ttl_seconds", 3600)
    expires_at = int(time.time()) + ttl

    with _LOCK:
        _TOKENS[token] = (client_id, expires_at)

    return {"access_token": token, "token_type": "bearer", "expires_in": ttl}


def validate_token(token: str):
    if not token:
        return False
    with _LOCK:
        data = _TOKENS.get(token)
        if not data:
            return False
        client_id, expires_at = data
        if int(time.time()) > expires_at:
            del _TOKENS[token]
            return False
        return True


def revoke_token(token: str):
    with _LOCK:
        if token in _TOKENS:
            del _TOKENS[token]
            return True
    return False
