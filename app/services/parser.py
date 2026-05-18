import xml.etree.ElementTree as ET
from app.models.payment import PaymentMessage

NS = {"ns": "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"}


def _find_text(root, xpath, default=""):
    element = root.find(xpath, NS)
    if element is None or element.text is None:
        return default
    return element.text.strip()


def parse_xml(xml_string):
    root = ET.fromstring(xml_string)

    # =========================
    # AMOUNTS
    # =========================
    amount_element = root.find(".//ns:InstdAmt", NS)
    intrbk_element = root.find(".//ns:IntrBkSttlmAmt", NS)

    # Accept either InstdAmt (preferred) or IntrBkSttlmAmt as amount source
    amount_source = amount_element if (amount_element is not None and amount_element.text) else intrbk_element
    if amount_source is None or amount_source.text is None:
        raise ValueError("Missing amount element (InstdAmt or IntrBkSttlmAmt)")

    amount = amount_source.text.strip()

    # ✔ SAFE CURRENCY RESOLUTION (SWIFT STYLE PRIORITY)
    currency = amount_source.get("Ccy") or ""

    # =========================
    # SENDER
    # =========================
    sender_name = _find_text(root, ".//ns:Dbtr/ns:Nm")
    sender_bic = _find_text(root, ".//ns:DbtrAgt/ns:FinInstnId/ns:BICFI")
    sender_account = _find_text(root, ".//ns:DbtrAcct/ns:Id/ns:IBAN")

    # =========================
    # RECEIVER
    # =========================
    receiver_name = _find_text(root, ".//ns:Cdtr/ns:Nm")
    receiver_bic = _find_text(root, ".//ns:CdtrAgt/ns:FinInstnId/ns:BICFI")
    receiver_account = _find_text(root, ".//ns:CdtrAcct/ns:Id/ns:Othr/ns:Id")

    # =========================
    # IDS
    # =========================
    message_id = _find_text(root, ".//ns:GrpHdr/ns:MsgId")
    instruction_id = _find_text(root, ".//ns:PmtId/ns:InstrId")
    creation_datetime = _find_text(root, ".//ns:GrpHdr/ns:CreDtTm")

    end_to_end_id = _find_text(root, ".//ns:PmtId/ns:EndToEndId")
    uetr = _find_text(root, ".//ns:PmtId/ns:UETR")

    # =========================
    # SETTLEMENT
    # =========================
    charge_bearer = _find_text(root, ".//ns:ChrgBr", "SHAR")
    settlement_method = _find_text(root, ".//ns:SttlmInf/ns:SttlmMtd")
    settlement_date = _find_text(root, ".//ns:IntrBkSttlmDt")

    # =========================
    # FINAL MODEL
    # =========================
    return PaymentMessage(
        message_id=message_id,
        instruction_id=instruction_id,
        creation_datetime=creation_datetime,

        end_to_end_id=end_to_end_id,
        uetr=uetr,

        charge_bearer=charge_bearer,
        settlement_method=settlement_method,
        settlement_date=settlement_date,

        sender_name=sender_name,
        sender_bic=sender_bic,
        sender_account=sender_account,

        receiver_name=receiver_name,
        receiver_bic=receiver_bic,
        receiver_account=receiver_account,

        amount=amount,
        currency=currency,

        remittance_info=_find_text(root, ".//ns:RmtInf/ns:Ustrd"),
    )