from app.core.config import get_bank_metadata

def get_bank_url(receiver_bic):
    bank = get_bank_metadata(receiver_bic)
    if not bank:
        return None
    return bank["url"]


def get_bank_info(receiver_bic):
    return get_bank_metadata(receiver_bic)


# ----------
# Routing with intermediaries
# ----------
from app.core.config import NETWORK


def get_route(sender_bic, receiver_bic):
    """Return a list of BICs representing a route from sender to receiver.

    If direct connection exists, returns [sender, receiver]. If no route,
    returns empty list.
    """
    if sender_bic == receiver_bic:
        return [sender_bic]

    # direct
    neighbors = NETWORK.get(sender_bic, [])
    if receiver_bic in neighbors:
        return [sender_bic, receiver_bic]

    # BFS
    from collections import deque

    queue = deque()
    queue.append((sender_bic, [sender_bic]))
    seen = {sender_bic}

    while queue:
        current, path = queue.popleft()
        for nb in NETWORK.get(current, []):
            if nb in seen:
                continue
            new_path = path + [nb]
            if nb == receiver_bic:
                return new_path
            seen.add(nb)
            queue.append((nb, new_path))

    return []