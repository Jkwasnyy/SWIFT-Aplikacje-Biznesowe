from flask import Flask, request
import sys
import os
from datetime import datetime
import requests

app = Flask(__name__)

def get_bank_name(port):
    return {
        3001: "Bank Polska 1",
        3002: "Bank Polska 2",
        3003: "Bank UK 1",
        3004: "Bank UK 2",
        3005: "Bank USA 1",
        3006: "Bank USA 2",
        3007: "Bank EU DE 1",
        3008: "Bank EU FR 1",
    }.get(port, f"Bank {port}")


@app.route("/receive", methods=["POST"])
def receive():

    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3001

    payload = request.data.decode("utf-8")

    message_id = request.headers.get("X-SWIFT-Message-Id", "unknown")
    currency = request.headers.get("X-SWIFT-Currency", "")
    uetr = request.headers.get("X-SWIFT-UETR", "")
    settlement_date = request.headers.get("X-SWIFT-Settlement-Date", "")
    receiver_account = request.headers.get("X-SWIFT-Receiver-Account", "")
    sender_account = request.headers.get("X-SWIFT-Sender-Account", "")
    callback_url = request.headers.get("X-SWIFT-Callback-Url", "")

    bank_name = get_bank_name(PORT)

    print(f"[{bank_name}] RECEIVED {datetime.utcnow().isoformat()}Z")
    print(f"Message-Id: {message_id}")
    print(f"UETR: {uetr}")
    print(f"Settlement-Date: {settlement_date}")
    print(f"Sender-Account: {sender_account}")
    print(f"Receiver-Account: {receiver_account}")
    print("CURRENCY HEADER:", currency)
    print(payload)

    if currency not in {"PLN", "EUR", "USD", "GBP"}:
        return {"status": "rejected", "reason": "unsupported_currency"}, 422

    if "<FIToFICstmrCdtTrf" not in payload:
        return {"status": "rejected", "reason": "invalid_pacs008"}, 400

    if "<UETR>" not in payload:
        return {"status": "rejected", "reason": "missing_uetr"}, 400

    if "<IntrBkSttlmAmt" not in payload:
        return {"status": "rejected", "reason": "missing_settlement_amount"}, 400

    closed_accounts = {
        "GB00CLOSED0000000000000000",
        "PL00000000000000000000000000",
        "DE00CLOSED00000000000000",
    }
    if receiver_account in closed_accounts:
        return {"status": "rejected", "reason": "receiver_account_closed"}, 422

    print("XML CHECK:", payload)

    if callback_url:
        ack_payload = {
            "status": "accepted",
            "bank": bank_name,
            "received_at": datetime.utcnow().isoformat() + "Z",
            "message_id": message_id,
            "uetr": uetr,
            "receiver_account": receiver_account,
        }
        try:
            callback_response = requests.post(callback_url, json=ack_payload, timeout=3.0)
            print(f"Callback sent to {callback_url} -> {callback_response.status_code}")
        except requests.RequestException as exc:
            print(f"Callback failed: {exc}")

    return {
        "status": "accepted",
        "bank": bank_name,
        "received_at": datetime.utcnow().isoformat() + "Z",
        "message_id": message_id,
        "uetr": uetr,
    }, 202


if __name__ == "__main__":
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3001
    bind_host = os.getenv("MOCK_BIND_HOST", "0.0.0.0")
    app.run(host=bind_host, port=PORT)