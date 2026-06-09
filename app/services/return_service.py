from app.core.config import get_bank_metadata
from app.core.logger import log
from app.services.forwarder import forward_message
from app.services.return_parser import is_return_message, parse_return_xml


def handle_payment_return(xml_data, headers=None):
    headers = headers or {}
    message_type = headers.get("X-SWIFT-Message-Type", "")

    try:
        parsed = parse_return_xml(xml_data)
    except Exception as exc:
        log(f"[RETURN_FAILED] REASON=InvalidReturnXML ERROR={exc}")
        return {"error": str(exc)}, 400

    if not is_return_message(parsed.get("remittance_info", ""), message_type):
        log(f"[RETURN_FAILED] UETR={parsed.get('uetr', '')} REASON=MissingZwrotMarker")
        return {
            "error": "Return message must include RmtInf/Ustrd with 'Zwrot' or header X-SWIFT-Message-Type: RETURN"
        }, 422

    original_sender_bic = parsed.get("original_sender_bic") or headers.get(
        "X-SWIFT-Original-Sender-BIC", ""
    )
    if not original_sender_bic:
        log(f"[RETURN_FAILED] UETR={parsed['uetr']} REASON=MissingOriginalSenderBIC")
        return {"error": "Missing original sender BIC (CdtrAgt/BICFI or X-SWIFT-Original-Sender-BIC)"}, 422

    sender_meta = get_bank_metadata(original_sender_bic)
    if not sender_meta or not sender_meta.get("url"):
        log(
            f"[RETURN_FAILED] UETR={parsed['uetr']} "
            f"ORIGINAL_SENDER={original_sender_bic} REASON=UnknownSenderBank"
        )
        return {"error": "Original sender bank not found"}, 404

    returning_bank_bic = parsed.get("returning_bank_bic") or headers.get(
        "X-SWIFT-Returning-Bank-BIC", ""
    )

    log(
        f"[RETURN_RECEIVED] UETR={parsed['uetr']} "
        f"FROM={returning_bank_bic} TO={original_sender_bic} "
        f"REASON={parsed.get('reason', '')} AMOUNT={parsed.get('amount', '')} "
        f"CURRENCY={parsed.get('currency', '')}"
    )

    forward_headers = {
        "X-SWIFT-Message-Type": "RETURN",
        "X-SWIFT-UETR": parsed["uetr"],
        "X-SWIFT-Message-Id": parsed.get("message_id", ""),
        "X-SWIFT-Return-Reason": parsed.get("reason", ""),
        "X-SWIFT-Returning-Bank-BIC": returning_bank_bic,
        "X-SWIFT-Original-Sender-BIC": original_sender_bic,
    }
    if parsed.get("currency"):
        forward_headers["X-SWIFT-Currency"] = parsed["currency"]

    try:
        status, resp = forward_message(
            sender_meta["url"],
            xml_data,
            headers=forward_headers,
        )
    except Exception as exc:
        log(f"[RETURN_FORWARD_ERROR] UETR={parsed['uetr']} ERROR={exc}")
        return {"error": str(exc)}, 502

    log(
        f"[RETURN_FORWARDED] UETR={parsed['uetr']} "
        f"TO={original_sender_bic} REASON={parsed.get('reason', '')} "
        f"STATUS={status} RESP={resp}"
    )

    if status >= 400:
        return {
            "error": "Sender bank rejected return notification",
            "uetr": parsed["uetr"],
            "forward_status": status,
            "forward_response": resp,
        }, 502

    return {
        "status": "return_forwarded",
        "uetr": parsed["uetr"],
        "original_sender_bic": original_sender_bic,
        "returning_bank_bic": returning_bank_bic,
        "reason": parsed.get("reason", ""),
    }, 200
