from flask import Flask, request
import sys
from datetime import datetime

app = Flask(__name__)


def get_bank_name(port):
    return {
        3001: "Bank Polska 1",
        3002: "Bank Polska 2",
        3003: "Bank UK 1",
        3004: "Bank UK 2",
        3005: "Bank USA 1",
        3006: "Bank USA 2",
    }.get(port, f"Bank {port}")

@app.route("/receive", methods=["POST"])
def receive():
    payload = request.data.decode("utf-8")
    message_id = request.headers.get("X-SWIFT-Message-Id", "unknown")
    currency = request.headers.get("X-SWIFT-Currency", "")
    bank_name = get_bank_name(PORT)

    print(f"[{bank_name}] RECEIVED {datetime.utcnow().isoformat()}Z")
    print(f"Message-Id: {message_id}")
    print(payload)

    if currency not in {"PLN", "EUR", "USD", "GBP"}:
        return {"status": "rejected", "reason": "unsupported_currency"}, 422

    if "<InstdAmt" not in payload:
        return {"status": "rejected", "reason": "invalid_payload"}, 400

    return {
        "status": "accepted",
        "bank": bank_name,
        "received_at": datetime.utcnow().isoformat() + "Z",
        "message_id": message_id,
    }, 202

if __name__ == "__main__":
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3001
    app.run(port=PORT)