from app.services.parser import parse_xml
from app.services.router import get_bank_info, get_route, estimate_route_seconds
from app.services.forwarder import forward_message
from app.core.logger import log
from app.services import scheduler
from app.services import inbox
from app.core.config import CANCEL_WINDOW_SECONDS
from app.services.settlement import calculate_fee_breakdown, format_fee_split, validate_receiver_account


def handle_swift_message(xml):
    try:
        message = parse_xml(xml)
        route = get_route(message.sender_bic, message.receiver_bic)
        if not route:
            log(
                f"[ROUTING_FAILED] MSG={message.message_id} UETR={message.uetr} FROM={message.sender_bic} TO={message.receiver_bic} REASON=NoRoute"
            )
            return {"error": "Route not found"}, 404

        fee_breakdown = calculate_fee_breakdown(message.charge_bearer, route, message.amount)
        estimated_seconds = estimate_route_seconds(route)

        # Notify banks that are expected to pay fees immediately (so they can include it
        # in any outgoing settlement). We notify sender and receiver if they have a non-zero share.
        def _fee_xml(uetr, amount, currency):
            return (
                f"<FIToFICstmrCdtTrf>"
                f"<UETR>{uetr}</UETR>"
                f"<IntrBkSttlmAmt Ccy=\"{currency}\">{amount}</IntrBkSttlmAmt>"
                f"</FIToFICstmrCdtTrf>"
            )

        try:
            # sender
            if float(fee_breakdown.get("sender_fee", "0.00")) > 0:
                sender_meta = get_bank_info(message.sender_bic)
                if sender_meta and sender_meta.get("url"):
                    xml_fee = _fee_xml(message.uetr, fee_breakdown["sender_fee"], message.currency)
                    headers = {
                        "X-SWIFT-UETR": message.uetr,
                        "X-SWIFT-Message-Id": message.message_id,
                        "X-SWIFT-Fee-For": "sender",
                        "X-SWIFT-Fee-Amount": fee_breakdown["sender_fee"],
                        "X-SWIFT-Currency": message.currency,
                    }
                    status, resp = forward_message(sender_meta["url"], xml_fee, headers=headers)
                    log(f"[FEE_NOTIFY] To sender {message.sender_bic} STATUS={status} RESP={resp}")

            # receiver
            if float(fee_breakdown.get("receiver_fee", "0.00")) > 0:
                recv_meta = get_bank_info(message.receiver_bic)
                if recv_meta and recv_meta.get("url"):
                    xml_fee = _fee_xml(message.uetr, fee_breakdown["receiver_fee"], message.currency)
                    headers = {
                        "X-SWIFT-UETR": message.uetr,
                        "X-SWIFT-Message-Id": message.message_id,
                        "X-SWIFT-Fee-For": "receiver",
                        "X-SWIFT-Fee-Amount": fee_breakdown["receiver_fee"],
                        "X-SWIFT-Currency": message.currency,
                    }
                    status, resp = forward_message(recv_meta["url"], xml_fee, headers=headers)
                    log(f"[FEE_NOTIFY] To receiver {message.receiver_bic} STATUS={status} RESP={resp}")
        except Exception as e:
            log(f"[FEE_NOTIFY_ERROR] {e}")

        # ===== RECEIVED STAGE =====
        log(
            f"[RECEIVED] MSG={message.message_id} "
            f"UETR={message.uetr} "
            f"SENDER={message.sender_bic} "
            f"AMOUNT={message.amount} "
            f"CURRENCY={message.currency} "
            f"CHRG={message.charge_bearer}"
        )

        # ===== VALIDATION STAGE =====
        if not message.sender_bic:
            log(f"[VALIDATION_FAILED] MSG={message.message_id} REASON=MissingSenderBIC")
            return {"error": "Missing sender bank"}, 400

        is_account_valid, account_reason = validate_receiver_account(message.receiver_bic, message.receiver_account)
        if not is_account_valid:
            log(
                f"[VALIDATION_FAILED] MSG={message.message_id} UETR={message.uetr} "
                f"REASON={account_reason} RECEIVER_BIC={message.receiver_bic} RECEIVER_ACCOUNT={message.receiver_account}"
            )
            if account_reason == "AccountClosed":
                return {"error": "Receiver account closed"}, 422
            return {"error": "Receiver account not found"}, 404

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
            f"BANK={bank_info['name']} "
            f"ROUTE={'>'.join(route)} "
            f"ETA_SECONDS={estimated_seconds:.2f} "
            f"FEE_TOTAL={fee_breakdown['total_fee']} "
            f"FEE_SPLIT={format_fee_split(fee_breakdown)}"
        )

        # ===== STORE IN INBOX (awaiting manual send) =====
        inbox.add_incoming(
            message.uetr,
            message,
            xml,
            route=route,
            fee_breakdown=fee_breakdown,
            estimated_seconds=estimated_seconds,
        )
        log(f"[INBOX] Stored incoming {message.uetr}")

        # ===== RETURN ACCEPTED (but not yet scheduled) =====
        return {
            "status": "accepted",
            "message_id": message.message_id,
            "uetr": message.uetr,
            "receiver_bank": bank_info["name"],
            "route": route,
            "estimated_seconds": estimated_seconds,
            "fee_breakdown": fee_breakdown,
            "cancel_window_seconds": CANCEL_WINDOW_SECONDS,
        }, 202

    except Exception as e:
        log(f"[SYSTEM_ERROR] ERROR={str(e)}")
        return {"error": str(e)}, 500