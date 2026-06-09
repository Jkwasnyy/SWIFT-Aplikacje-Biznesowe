import threading
from typing import Dict

from app.core.config import FORWARD_DELAY_SECONDS
from app.core.config import BANK_ACK_CALLBACK_URL, BANK_RETURN_CALLBACK_URL
from app.core.logger import log
from app.services.router import get_route, get_bank_metadata
from app.services.forwarder import forward_message
from app.services.settlement import validate_receiver_account

# pending: uetr -> {"message": PaymentMessage, "xml": str, "timer": Timer, "cancelled": bool}
_PENDING: Dict[str, Dict] = {}
_LOCK = threading.Lock()


def schedule_forward(message, xml, metadata=None):
    uetr = message.uetr
    metadata = metadata or {}

    is_account_valid, account_reason = validate_receiver_account(message.receiver_bic, message.receiver_account)
    if not is_account_valid:
        log(
            f"[VALIDATION_FAILED] MSG={message.message_id} UETR={uetr} REASON={account_reason} "
            f"RECEIVER_BIC={message.receiver_bic} RECEIVER_ACCOUNT={message.receiver_account}"
        )
        return {"uetr": uetr, "error": account_reason}

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
                is_final_hop = hop_bic == route[-1]
                callback_url = BANK_ACK_CALLBACK_URL if is_final_hop else None
                return_callback_url = BANK_RETURN_CALLBACK_URL if is_final_hop else None
                log(f"[SCHEDULER] Forwarding {uetr} to {hop_bic} @ {url}")
                headers = {
                    "X-SWIFT-UETR": uetr,
                    "X-SWIFT-Message-Id": message.message_id,
                    "X-SWIFT-Charge-Bearer": message.charge_bearer,
                    "X-SWIFT-Currency": message.currency,
                    "X-SWIFT-Settlement-Date": message.settlement_date,
                    "X-SWIFT-Sender-Account": message.sender_account,
                    "X-SWIFT-Receiver-Account": message.receiver_account,
                }
                # include fee breakdown headers when forwarding
                fee = entry.get("fee_breakdown", {})
                if fee:
                    headers["X-SWIFT-Fee-Total"] = fee.get("total_fee", "0.00")
                    headers["X-SWIFT-Fee-Sender"] = fee.get("sender_fee", "0.00")
                    headers["X-SWIFT-Fee-Receiver"] = fee.get("receiver_fee", "0.00")
                    headers["X-SWIFT-Fee-Intermediary"] = fee.get("intermediary_fee", "0.00")
                if callback_url:
                    headers["X-SWIFT-Callback-Url"] = callback_url
                if return_callback_url:
                    headers["X-SWIFT-Return-Url"] = return_callback_url
                status, resp = forward_message(
                    url,
                    xml,
                    headers=headers,
                )
                last_response = (status, resp)

                if status >= 400:
                    log(
                        f"[SETTLEMENT_FAILED] MSG={message.message_id} UETR={uetr} "
                        f"HOP={hop_bic} STATUS={status} REASON={resp}"
                    )
                    break

            if last_response and 200 <= last_response[0] < 300:
                log(
                    f"[COMPLETED] MSG={message.message_id} UETR={uetr} "
                    f"STATUS=completed BANK_RESPONSE={last_response[0]}"
                )

            log(f"[SCHEDULER] Finished forward for {uetr} - last_status={last_response}")
        except Exception as e:
            log(f"[SCHEDULER][ERROR] {e}")

        with _LOCK:
            if uetr in _PENDING:
                del _PENDING[uetr]

    timer = threading.Timer(FORWARD_DELAY_SECONDS, _do_forward)

    with _LOCK:
        _PENDING[uetr] = {
            "message": message,
            "xml": xml,
            "timer": timer,
            "cancelled": False,
            "route": metadata.get("route", get_route(message.sender_bic, message.receiver_bic)),
            "fee_breakdown": metadata.get("fee_breakdown", getattr(message, "fee_breakdown", {})),
            "estimated_seconds": metadata.get(
                "estimated_seconds",
                getattr(message, "estimated_seconds", 0.0),
            ),
        }
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
            route = get_route(getattr(msg, "sender_bic", ""), getattr(msg, "receiver_bic", ""))
            result.append(
                {
                    "uetr": uetr,
                    "message_id": getattr(msg, "message_id", None),
                    "from": getattr(msg, "sender_bic", None),
                    "to": getattr(msg, "receiver_bic", None),
                    "route": route,
                    "estimated_seconds": entry.get("estimated_seconds", 0.0),
                    "fee_breakdown": entry.get("fee_breakdown", {}),
                    "cancelled": bool(entry.get("cancelled", False)),
                }
            )
    return result
