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


# -----------------------------
# Network topology and OAuth2
# -----------------------------
# Adjacency list of bank connectivity. Use this to compute multi-hop routes
# between banks when no direct connection exists.
NETWORK = {
    # PLBANK1 connects directly to PLBANK2 and UKBANK1
    "PLBANK1XXX": ["PLBANK2XXX", "UKBANK1XXX"],
    "PLBANK2XXX": ["PLBANK1XXX", "USBANK1XXX"],
    "UKBANK1XXX": ["UKBANK2XXX", "PLBANK1XXX"],
    "UKBANK2XXX": ["UKBANK1XXX", "USBANK2XXX"],
    "USBANK1XXX": ["PLBANK2XXX", "USBANK2XXX"],
    "USBANK2XXX": ["USBANK1XXX", "UKBANK2XXX"],
}


# Mock OAuth2 configuration (student project). In a real deployment these
# values would be stored securely and OAuth flows handled by an identity
# provider. This mock allows issuing short-lived bearer tokens for API calls.
OAUTH = {
    "token_ttl_seconds": 3600,
    "clients": {"test-client": "test-secret"},
}


# Forwarding / cancellation policy
FORWARD_DELAY_SECONDS = 5  # seconds to wait before forwarding (cancel window)
CANCEL_WINDOW_SECONDS = FORWARD_DELAY_SECONDS  # same period allowed for cancel