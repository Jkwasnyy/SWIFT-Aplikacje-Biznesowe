import os


# Hostname used by app when forwarding to mock banks. For local runs keep
# localhost; in Docker Compose this can point to another service.
BANK_HOST = os.getenv("BANK_HOST", "localhost")

# Hostname used by mock banks when sending callbacks to the main app.
APP_HOST = os.getenv("APP_HOST", "localhost")

BANK_METADATA = {
    # BIC-like identifiers (4 char bank code + 2 char country + 2 char location + optional branch)
    "PLBKPL01XXX": {"name": "Bank Polska 1", "country": "PL", "url": f"http://{BANK_HOST}:3001/receive"},
    "PLBKPL02XXX": {"name": "Bank Polska 2", "country": "PL", "url": f"http://{BANK_HOST}:3002/receive"},
    "UKBKGB01XXX": {"name": "Bank UK 1", "country": "GB", "url": f"http://{BANK_HOST}:3003/receive"},
    "UKBKGB02XXX": {"name": "Bank UK 2", "country": "GB", "url": f"http://{BANK_HOST}:3004/receive"},
    "USBKUS01XXX": {"name": "Bank USA 1", "country": "US", "url": f"http://{BANK_HOST}:3005/receive"},
    "USBKUS02XXX": {"name": "Bank USA 2", "country": "US", "url": f"http://{BANK_HOST}:3006/receive"},
}

BANKS = {bic: data["url"] for bic, data in BANK_METADATA.items()}


def get_bank_metadata(bic):
    return BANK_METADATA.get(bic)


# Known accounts used by the simulator. Closed and missing accounts are used
# to exercise error handling in the transfer flow.
ACCOUNT_DIRECTORY = {
    "PLBKPL01XXX": {
        "PL61109010140000071219812874": "open",
    },
    "PLBKPL02XXX": {
        "PL62109010140000071219812875": "open",
        "PL00000000000000000000000000": "closed",
    },
    "UKBKGB01XXX": {
        "GB29NWBK60161331926819": "open",
        "GB00CLOSED0000000000000000": "closed",
    },
    "UKBKGB02XXX": {
        "GB29NWBK60161331926820": "open",
    },
    "USBKUS01XXX": {
        "US123456789012345678901234": "open",
    },
    "USBKUS02XXX": {
        "US223456789012345678901234": "open",
    },
}


def get_account_status(bic, account_number):
    accounts = ACCOUNT_DIRECTORY.get(bic, {})
    return accounts.get(account_number)


# -----------------------------
# Network topology and OAuth2
# -----------------------------
# Adjacency list of bank connectivity. Use this to compute multi-hop routes
# between banks when no direct connection exists.
NETWORK = {
    # PLBKPL01XXX connects to PLBKPL02XXX and UKBKGB01XXX
    "PLBKPL01XXX": ["PLBKPL02XXX", "UKBKGB01XXX"],
    "PLBKPL02XXX": ["PLBKPL01XXX", "USBKUS01XXX"],
    "UKBKGB01XXX": ["UKBKGB02XXX", "PLBKPL01XXX"],
    "UKBKGB02XXX": ["UKBKGB01XXX", "USBKUS02XXX"],
    "USBKUS01XXX": ["PLBKPL02XXX", "USBKUS02XXX"],
    "USBKUS02XXX": ["USBKUS01XXX", "UKBKGB02XXX"],
}

# Weighted latency graph used by route selection. Lower cost means a faster
# expected payment path, even if it uses more intermediaries.
NETWORK_LATENCY_SECONDS = {
    "PLBKPL01XXX": {"PLBKPL02XXX": 5.0, "UKBKGB01XXX": 1.0},
    "PLBKPL02XXX": {"PLBKPL01XXX": 5.0, "USBKUS01XXX": 5.0},
    "UKBKGB01XXX": {"UKBKGB02XXX": 1.0, "PLBKPL01XXX": 1.0},
    "UKBKGB02XXX": {"UKBKGB01XXX": 1.0, "USBKUS02XXX": 1.0},
    "USBKUS01XXX": {"PLBKPL02XXX": 5.0, "USBKUS02XXX": 1.0},
    "USBKUS02XXX": {"USBKUS01XXX": 1.0, "UKBKGB02XXX": 1.0},
}


PAYMENT_FEES = {
    "base_fee": 0.50,
    "per_hop_fee": 0.25,
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

# Bank callback endpoint used by mock banks to confirm receipt of a transfer.
BANK_ACK_CALLBACK_URL = f"http://{APP_HOST}:3000/api/bank/ack"