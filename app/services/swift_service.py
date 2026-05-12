from app.services.parser import parse_xml
from app.services.router import get_bank_info, get_bank_url
from app.services.forwarder import forward_message
from app.core.logger import log

def handle_swift_message(xml):
    try:
        message = parse_xml(xml)

        if not message.sender_bic:
            log("Missing sender BIC")
            return {"error": "Missing sender bank"}, 400

        bank_info = get_bank_info(message.receiver_bic)
        if not bank_info:
            log(f"Unknown receiver bank: {message.receiver_bic}")
            return {"error": "Bank not found"}, 404

        log(
            f"{message.sender_bic} -> {message.receiver_bic} | {message.amount} {message.currency} | {message.message_id}"
        )

        bank_url = get_bank_url(message.receiver_bic)

        status, response_text = forward_message(
            bank_url,
            xml,
            headers={
                "X-SWIFT-Message-Id": message.message_id,
                "X-SWIFT-Instruction-Id": message.instruction_id,
                "X-SWIFT-Charge-Bearer": message.charge_bearer,
                "X-SWIFT-Sender-BIC": message.sender_bic,
                "X-SWIFT-Receiver-BIC": message.receiver_bic,
                "X-SWIFT-Currency": message.currency,
            },
        )

        log(f"Forwarded to {bank_info['name']} ({bank_url}) | status {status}")
        if response_text:
            log(f"Bank response: {response_text}")

        return {
            "status": "submitted",
            "message_id": message.message_id,
            "forwarded_to": bank_url,
            "receiver_bank": bank_info["name"],
            "bank_response_status": status,
        }, 200

    except Exception as e:
        log(str(e))
        return {"error": str(e)}, 500