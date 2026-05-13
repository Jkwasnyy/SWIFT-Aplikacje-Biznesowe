from app.services.parser import parse_xml
from app.services.router import get_bank_info, get_bank_url
from app.services.forwarder import forward_message
from app.core.logger import log


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

        # ===== FORWARDING STAGE =====
        bank_url = get_bank_url(message.receiver_bic)

        status, response_text = forward_message(
            bank_url,
            xml,
            headers={
                "X-SWIFT-UETR": message.uetr,
                "X-SWIFT-Message-Id": message.message_id,
                "X-SWIFT-Instruction-Id": message.instruction_id,
                "X-SWIFT-Charge-Bearer": message.charge_bearer,
                # --- DODAJ TE LINIE ---
                "X-SWIFT-Currency": message.currency,
                "X-SWIFT-Settlement-Date": message.settlement_date,
                # ----------------------
            },
        )

        log(
            f"[FORWARDED] MSG={message.message_id} "
            f"UETR={message.uetr} "
            f"TO={bank_info['name']} "
            f"URL={bank_url} "
            f"STATUS={status}"
        )

        # ===== RESPONSE STAGE =====
        if response_text:
            log(
                f"[BANK_RESPONSE] MSG={message.message_id} "
                f"UETR={message.uetr} "
                f"RESPONSE={response_text}"
            )

        # ===== FINAL =====
        log(
            f"[COMPLETED] MSG={message.message_id} "
            f"UETR={message.uetr} "
            f"STATUS=SUBMITTED"
        )

        return {
            "status": "submitted",
            "message_id": message.message_id,
            "uetr": message.uetr,
            "forwarded_to": bank_url,
            "receiver_bank": bank_info["name"],
            "bank_response_status": status,
        }, 200

    except Exception as e:
        log(f"[SYSTEM_ERROR] ERROR={str(e)}")
        return {"error": str(e)}, 500