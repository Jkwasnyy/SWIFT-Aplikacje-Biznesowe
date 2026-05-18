import threading
import time
from typing import Dict

from app.core.config import FORWARD_DELAY_SECONDS
from app.core.logger import log
from app.services.router import get_route, get_bank_metadata
from app.services.forwarder import forward_message

# pending: uetr -> {"message": PaymentMessage, "xml": str, "timer": Timer, "cancelled": bool}
_PENDING: Dict[str, Dict] = {}
_LOCK = threading.Lock()


def schedule_forward(message, xml):
    uetr = message.uetr

    def _do_forward():
        with _LOCK:
            entry = _PENDING.get(uetr)
            if not entry:
                log(f"[SCHEDULER] No pending entry for {uetr}")
                return
            if entry.get("cancelled"):
                log(f"[SCHEDULER] Cancelled, skipping forward {uetr}")
                del _PENDING[uetr]
                return

        log(f"[SCHEDULER] Starting forward for {uetr}")

        try:
            route = get_route(message.sender_bic, message.receiver_bic)
            # route is list of BICs including sender and receiver
            last_response = None
            for hop_bic in route[1:]:
                meta = get_bank_metadata(hop_bic)
                if not meta:
                    log(f"[SCHEDULER] Missing metadata for hop {hop_bic}")
                    continue
                url = meta.get("url")
                log(f"[SCHEDULER] Forwarding {uetr} to {hop_bic} @ {url}")
                status, resp = forward_message(
                    url,
                    xml,
                    headers={
                        "X-SWIFT-UETR": uetr,
                        "X-SWIFT-Message-Id": message.message_id,
                        "X-SWIFT-Charge-Bearer": message.charge_bearer,
                        "X-SWIFT-Currency": message.currency,
                        "X-SWIFT-Settlement-Date": message.settlement_date,
                    },
                )
                last_response = (status, resp)

            log(f"[SCHEDULER] Finished forward for {uetr} - last_status={last_response}")
        except Exception as e:
            log(f"[SCHEDULER][ERROR] {e}")

        with _LOCK:
            if uetr in _PENDING:
                del _PENDING[uetr]

    timer = threading.Timer(FORWARD_DELAY_SECONDS, _do_forward)

    with _LOCK:
        _PENDING[uetr] = {"message": message, "xml": xml, "timer": timer, "cancelled": False}
        timer.start()

    log(f"[SCHEDULER] Scheduled forward for {uetr} in {FORWARD_DELAY_SECONDS}s")
    return {"uetr": uetr, "scheduled_in_secs": FORWARD_DELAY_SECONDS}


def cancel_pending(uetr: str):
    with _LOCK:
        entry = _PENDING.get(uetr)
        if not entry:
            return False
        entry["cancelled"] = True
        timer = entry.get("timer")
        if timer and timer.is_alive():
            timer.cancel()
        del _PENDING[uetr]
    log(f"[SCHEDULER] Cancelled pending {uetr}")
    return True


def list_pending():
    """Return a shallow summary of pending scheduled forwards."""
    with _LOCK:
        result = []
        for uetr, entry in _PENDING.items():
            msg = entry.get("message")
            result.append(
                {
                    "uetr": uetr,
                    "message_id": getattr(msg, "message_id", None),
                    "from": getattr(msg, "sender_bic", None),
                    "to": getattr(msg, "receiver_bic", None),
                    "cancelled": bool(entry.get("cancelled", False)),
                }
            )
    return result
