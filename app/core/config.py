BANK_METADATA = {
    "PLBANK1XXX": {"name": "Bank Polska 1", "country": "PL", "url": "http://localhost:3001/receive"},
    "PLBANK2XXX": {"name": "Bank Polska 2", "country": "PL", "url": "http://localhost:3002/receive"},
    "UKBANK1XXX": {"name": "Bank UK 1", "country": "UK", "url": "http://localhost:3003/receive"},
    "UKBANK2XXX": {"name": "Bank UK 2", "country": "UK", "url": "http://localhost:3004/receive"},
    "USBANK1XXX": {"name": "Bank USA 1", "country": "US", "url": "http://localhost:3005/receive"},
    "USBANK2XXX": {"name": "Bank USA 2", "country": "US", "url": "http://localhost:3006/receive"},
}

BANKS = {bic: data["url"] for bic, data in BANK_METADATA.items()}


def get_bank_metadata(bic):
    return BANK_METADATA.get(bic)