from threading import Lock

# Simple in-memory inbox for received messages waiting for manual send
_lock = Lock()
_inbox = {}


def add_incoming(uetr, message_obj, xml, **metadata):
    with _lock:
        _inbox[uetr] = {
            "message": message_obj,
            "xml": xml,
            **metadata,
        }


def list_incoming():
    with _lock:
        result = []
        for uetr, entry in _inbox.items():
            message = entry["message"]
            result.append(
                {
                    "uetr": uetr,
                    "message_id": getattr(message, "message_id", ""),
                    "sender": getattr(message, "sender_bic", ""),
                    "receiver": getattr(message, "receiver_bic", ""),
                    "amount": getattr(message, "amount", ""),
                    "currency": getattr(message, "currency", ""),
                    "route": entry.get("route", []),
                    "fee_breakdown": entry.get("fee_breakdown", {}),
                    "estimated_seconds": entry.get("estimated_seconds", 0.0),
                }
            )
        return result


def get_incoming(uetr):
    with _lock:
        return _inbox.get(uetr)


def pop_incoming(uetr):
    with _lock:
        return _inbox.pop(uetr, None)
