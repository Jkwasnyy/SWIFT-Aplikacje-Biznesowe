from flask import Flask, request
import sys
import os
from datetime import datetime
import requests

app = Flask(__name__)

PORT_TO_BIC = {
    3001: "PLBKPL01XXX",
    3002: "PLBKPL02XXX",
    3003: "UKBKGB01XXX",
    3004: "UKBKGB02XXX",
    3005: "USBKUS01XXX",
    3006: "USBKUS02XXX",
    3007: "DEBKDE01XXX",
    3008: "EUBKFR01XXX",
}


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


def build_return_xml(uetr, message_id, reason, returning_bic, original_sender_bic, amount, currency):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf>
    <GrpHdr>
      <MsgId>RETURN-{message_id}</MsgId>
      <CreDtTm>{datetime.utcnow().isoformat()}Z</CreDtTm>
    </GrpHdr>
    <CdtTrfTxInf>
      <PmtId>
        <InstrId>RETURN-{message_id}</InstrId>
        <UETR>{uetr}</UETR>
      </PmtId>
      <IntrBkSttlmAmt Ccy="{currency}">{amount}</IntrBkSttlmAmt>
      <RmtInf>
        <Ustrd>Zwrot</Ustrd>
      </RmtInf>
      <ReturnInf>
        <Rsn>{reason}</Rsn>
      </ReturnInf>
      <DbtrAgt>
        <FinInstnId>
          <BICFI>{returning_bic}</BICFI>
        </FinInstnId>
      </DbtrAgt>
      <CdtrAgt>
        <FinInstnId>
          <BICFI>{original_sender_bic}</BICFI>
        </FinInstnId>
      </CdtrAgt>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>"""


def send_return_to_middleware(return_url, return_xml, headers):
    try:
        response = requests.post(
            return_url,
            data=return_xml,
            headers=headers,
            timeout=3.0,
        )
        print(f"Return sent to {return_url} -> {response.status_code} {response.text}")
        return response.status_code, response.text
    except requests.RequestException as exc:
        print(f"Return callback failed: {exc}")
        return None, str(exc)


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
    return_url = request.headers.get("X-SWIFT-Return-Url", "")
    message_type = request.headers.get("X-SWIFT-Message-Type", "")
    return_reason = request.headers.get("X-SWIFT-Return-Reason", "")

    bank_name = get_bank_name(PORT)
    bank_bic = PORT_TO_BIC.get(PORT, "")

    print(f"[{bank_name}] RECEIVED {datetime.utcnow().isoformat()}Z")
    print(f"Message-Type: {message_type or 'PAYMENT'}")
    print(f"Message-Id: {message_id}")
    print(f"UETR: {uetr}")
    print(f"Settlement-Date: {settlement_date}")
    print(f"Sender-Account: {sender_account}")
    print(f"Receiver-Account: {receiver_account}")
    print("CURRENCY HEADER:", currency)
    print(payload)

    if message_type.upper() == "RETURN":
        print(f"[{bank_name}] RETURN received for UETR={uetr} REASON={return_reason}")
        return {
            "status": "return_received",
            "bank": bank_name,
            "received_at": datetime.utcnow().isoformat() + "Z",
            "message_id": message_id,
            "uetr": uetr,
            "return_reason": return_reason,
        }, 202

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
        reason = "receiver_account_closed"
        if return_url:
            original_sender_bic = ""
            if "<DbtrAgt>" in payload and "<BICFI>" in payload:
                start = payload.find("<DbtrAgt>")
                end = payload.find("</DbtrAgt>", start)
                segment = payload[start:end] if end != -1 else payload[start:]
                bic_start = segment.find("<BICFI>") + len("<BICFI>")
                bic_end = segment.find("</BICFI>", bic_start)
                if bic_start > len("<BICFI>") - 1 and bic_end != -1:
                    original_sender_bic = segment[bic_start:bic_end].strip()

            amount = "0.00"
            if "<IntrBkSttlmAmt" in payload:
                amt_start = payload.find(">", payload.find("<IntrBkSttlmAmt")) + 1
                amt_end = payload.find("</IntrBkSttlmAmt>", amt_start)
                if amt_end != -1:
                    amount = payload[amt_start:amt_end].strip()

            return_xml = build_return_xml(
                uetr=uetr,
                message_id=message_id,
                reason=reason,
                returning_bic=bank_bic,
                original_sender_bic=original_sender_bic,
                amount=amount,
                currency=currency or "PLN",
            )
            send_return_to_middleware(
                return_url,
                return_xml,
                headers={
                    "Content-Type": "application/xml",
                    "X-SWIFT-Message-Type": "RETURN",
                    "X-SWIFT-UETR": uetr,
                    "X-SWIFT-Returning-Bank-BIC": bank_bic,
                    "X-SWIFT-Original-Sender-BIC": original_sender_bic,
                },
            )
        return {"status": "rejected", "reason": reason}, 422

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
