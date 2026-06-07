from decimal import Decimal, ROUND_HALF_UP

from app.core.config import PAYMENT_FEES, get_account_status, get_bank_metadata, PAYMENT_FEE_PERCENT


def _money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_fee_breakdown(charge_bearer, route, amount):
    """Calculate fees as a percentage of the payment `amount`.

    Returns amounts as strings formatted to two decimals (same shape as before).
    """
    # Ensure Decimal amount
    amt = Decimal(str(amount))

    # total fee is a flat percentage of the payment amount
    total_fee = _money(amt * Decimal(str(PAYMENT_FEE_PERCENT)))

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
    hop_count = max(len(route) - 1, 1)

    return {
        "charge_bearer": charge_bearer,
        "total_fee": f"{total_fee:.2f}",
        "sender_fee": f"{sender_fee:.2f}",
        "receiver_fee": f"{receiver_fee:.2f}",
        "intermediary_fee": f"{intermediary_fee:.2f}",
        "hop_count": hop_count,
    }


def validate_receiver_account(receiver_bic, receiver_account):
    bank_meta = get_bank_metadata(receiver_bic)
    if bank_meta and bank_meta.get("external"):
        if not receiver_account:
            return False, "AccountNotFound"
        return True, "OK"

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