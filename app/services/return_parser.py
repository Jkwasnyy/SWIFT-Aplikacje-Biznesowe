import xml.etree.ElementTree as ET

NS = {"ns": "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"}


def _find_text(root, xpath, default=""):
    element = root.find(xpath, NS)
    if element is None or element.text is None:
        return default
    return element.text.strip()


def parse_return_xml(xml_string):
    root = ET.fromstring(xml_string)

    uetr = _find_text(root, ".//ns:PmtId/ns:UETR")
    if not uetr:
        raise ValueError("Missing UETR in return message")

    remittance = _find_text(root, ".//ns:RmtInf/ns:Ustrd")
    reason = _find_text(root, ".//ns:ReturnInf/ns:Rsn") or _find_text(
        root, ".//ns:RejectionReason"
    )

    returning_bank_bic = _find_text(root, ".//ns:DbtrAgt/ns:FinInstnId/ns:BICFI")
    original_sender_bic = _find_text(root, ".//ns:CdtrAgt/ns:FinInstnId/ns:BICFI")

    amount_element = root.find(".//ns:IntrBkSttlmAmt", NS)
    amount = ""
    currency = ""
    if amount_element is not None and amount_element.text:
        amount = amount_element.text.strip()
        currency = amount_element.get("Ccy", "")

    message_id = _find_text(root, ".//ns:GrpHdr/ns:MsgId")

    return {
        "uetr": uetr,
        "message_id": message_id,
        "remittance_info": remittance,
        "reason": reason,
        "returning_bank_bic": returning_bank_bic,
        "original_sender_bic": original_sender_bic,
        "amount": amount,
        "currency": currency,
    }


def is_return_message(remittance_info="", message_type_header=""):
    if message_type_header.upper() == "RETURN":
        return True
    return "zwrot" in (remittance_info or "").lower()
