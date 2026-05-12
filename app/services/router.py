from app.core.config import get_bank_metadata

def get_bank_url(receiver_bic):
    bank = get_bank_metadata(receiver_bic)
    if not bank:
        return None
    return bank["url"]


def get_bank_info(receiver_bic):
    return get_bank_metadata(receiver_bic)