from decimal import Decimal, ROUND_HALF_UP

from app.core.config import PAYMENT_FEES, get_account_status


def _money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_fee_breakdown(charge_bearer, route):
    hop_count = max(len(route) - 1, 1)
    total_fee = _money(PAYMENT_FEES["base_fee"] + PAYMENT_FEES["per_hop_fee"] * hop_count)

    charge_bearer = (charge_bearer or "SHAR").upper()
    if charge_bearer == "DEBT":
        sender_fee = total_fee
        receiver_fee = Decimal("0.00")
    elif charge_bearer == "CRED":
        sender_fee = Decimal("0.00")
        receiver_fee = total_fee
    elif charge_bearer == "SLEV":
        sender_fee = _money(total_fee * Decimal("0.70"))
        receiver_fee = total_fee - sender_fee
    else:
        sender_fee = _money(total_fee * Decimal("0.50"))
        receiver_fee = total_fee - sender_fee

    intermediary_fee = total_fee - sender_fee - receiver_fee
    return {
        "charge_bearer": charge_bearer,
        "total_fee": f"{total_fee:.2f}",
        "sender_fee": f"{sender_fee:.2f}",
        "receiver_fee": f"{receiver_fee:.2f}",
        "intermediary_fee": f"{intermediary_fee:.2f}",
        "hop_count": hop_count,
    }


def validate_receiver_account(receiver_bic, receiver_account):
    status = get_account_status(receiver_bic, receiver_account)
    if status is None:
        return False, "AccountNotFound"
    if status != "open":
        return False, "AccountClosed"
    return True, "OK"


def format_fee_split(fee_breakdown):
    return (
        f"sender:{fee_breakdown['sender_fee']}/"
        f"receiver:{fee_breakdown['receiver_fee']}/"
        f"intermediary:{fee_breakdown['intermediary_fee']}"
    )