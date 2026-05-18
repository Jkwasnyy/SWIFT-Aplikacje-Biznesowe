from threading import Lock

# Simple in-memory inbox for received messages waiting for manual send
_lock = Lock()
_inbox = {}


def add_incoming(uetr, message_obj, xml):
    with _lock:
        _inbox[uetr] = {
            "message": message_obj,
            "xml": xml,
        }


def list_incoming():
    with _lock:
        return [{"uetr": k, "message_id": v["message"].message_id if hasattr(v["message"], 'message_id') else "", "sender": getattr(v["message"], 'sender', '')} for k, v in _inbox.items()]


def get_incoming(uetr):
    with _lock:
        return _inbox.get(uetr)


def pop_incoming(uetr):
    with _lock:
        return _inbox.pop(uetr, None)
