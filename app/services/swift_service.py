from app.services.parser import parse_xml
from app.services.router import get_bank_info
from app.services.forwarder import forward_message
from app.core.logger import log
from app.services import scheduler
from app.services import inbox
from app.core.config import CANCEL_WINDOW_SECONDS


def handle_swift_message(xml):
    try:
        message = parse_xml(xml)

        # ===== RECEIVED STAGE =====
        log(
            f"[RECEIVED] MSG={message.message_id} "
            f"UETR={message.uetr} "
            f"SENDER={message.sender_bic} "
            f"AMOUNT={message.amount} {message.currency}"
        )

        # ===== VALIDATION STAGE =====
        if not message.sender_bic:
            log(f"[VALIDATION_FAILED] MSG={message.message_id} REASON=MissingSenderBIC")
            return {"error": "Missing sender bank"}, 400

        log(f"[VALIDATION_OK] MSG={message.message_id} UETR={message.uetr}")

        # ===== ROUTING STAGE =====
        bank_info = get_bank_info(message.receiver_bic)
        if not bank_info:
            log(
                f"[ROUTING_FAILED] MSG={message.message_id} "
                f"UETR={message.uetr} "
                f"RECEIVER_BIC={message.receiver_bic} "
                f"REASON=UnknownBank"
            )
            return {"error": "Bank not found"}, 404

        log(
            f"[ROUTED] MSG={message.message_id} "
            f"UETR={message.uetr} "
            f"FROM={message.sender_bic} "
            f"TO={message.receiver_bic} "
            f"BANK={bank_info['name']}"
        )

        # ===== STORE IN INBOX (awaiting manual send) =====
        inbox.add_incoming(message.uetr, message, xml)
        log(f"[INBOX] Stored incoming {message.uetr}")

        # ===== RETURN ACCEPTED (but not yet scheduled) =====
        return {
            "status": "accepted",
            "message_id": message.message_id,
            "uetr": message.uetr,
            "receiver_bank": bank_info["name"],
            "scheduled_in": None,
            "cancel_window_seconds": CANCEL_WINDOW_SECONDS,
        }, 202

    except Exception as e:
        log(f"[SYSTEM_ERROR] ERROR={str(e)}")
        return {"error": str(e)}, 500