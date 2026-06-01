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
from app.core.config import NETWORK_LATENCY_SECONDS, DEFAULT_ESTIMATED_SECONDS


def estimate_route_seconds(route):
    # If no real route (same bank) return 0
    if not route or len(route) < 2:
        return 0.0

    total = 0.0
    for left_bic, right_bic in zip(route, route[1:]):
        total += NETWORK_LATENCY_SECONDS.get(left_bic, {}).get(right_bic, 1.0)

    # Ensure the estimated time is at least the default configured seconds
    estimated = max(total, DEFAULT_ESTIMATED_SECONDS)
    return round(estimated, 2)


def get_route(sender_bic, receiver_bic):
    """Return the fastest route between sender and receiver.

    The path is selected using weighted shortest-path search so the simulator
    prefers the route with the lowest expected settlement time, not just the
    route with the fewest hops.
    """
    if sender_bic == receiver_bic:
        return [sender_bic]

    import heapq

    queue = [(0.0, sender_bic, [sender_bic])]
    best_costs = {sender_bic: 0.0}

    while queue:
        current_cost, current_bic, path = heapq.heappop(queue)
        if current_bic == receiver_bic:
            return path

        if current_cost > best_costs.get(current_bic, float("inf")):
            continue

        for neighbor in NETWORK.get(current_bic, []):
            edge_cost = NETWORK_LATENCY_SECONDS.get(current_bic, {}).get(neighbor, 1.0)
            new_cost = current_cost + edge_cost
            if new_cost >= best_costs.get(neighbor, float("inf")):
                continue
            best_costs[neighbor] = new_cost
            heapq.heappush(queue, (new_cost, neighbor, path + [neighbor]))

    return []