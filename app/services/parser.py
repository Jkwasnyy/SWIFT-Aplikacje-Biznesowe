import xml.etree.ElementTree as ET

from app.models.payment import PaymentMessage


def _find_text(root, xpath, default=""):
    element = root.find(xpath)
    if element is None or element.text is None:
        return default
    return element.text.strip()


def parse_xml(xml_string):
    root = ET.fromstring(xml_string)

    amount_element = root.find(".//InstdAmt")
    if amount_element is None or amount_element.text is None:
        raise ValueError("Missing instructed amount")

    sender_name = _find_text(root, ".//Dbtr/Nm")
    sender_bic = _find_text(root, ".//DbtrAgt//BICFI", sender_name)
    receiver_name = _find_text(root, ".//Cdtr/Nm")
    receiver_bic = _find_text(root, ".//CdtrAgt//BICFI", receiver_name)

    return PaymentMessage(
        message_id=_find_text(root, ".//GrpHdr/MsgId"),
        instruction_id=_find_text(root, ".//PmtId/InstrId"),
        creation_datetime=_find_text(root, ".//GrpHdr/CreDtTm"),
        charge_bearer=_find_text(root, ".//ChrgBr", "SLEV"),
        sender_name=sender_name,
        sender_bic=sender_bic,
        receiver_name=receiver_name,
        receiver_bic=receiver_bic,
        amount=amount_element.text.strip(),
        currency=amount_element.attrib.get("Ccy", "").strip(),
        remittance_info=_find_text(root, ".//RmtInf/Ustrd"),
    )