from flask import Blueprint, send_from_directory, jsonify, request
import os
import re
from collections import OrderedDict
from app.services import scheduler
from app.services import inbox
from app.services.router import get_route
from app.core.auth import issue_token

ui_bp = Blueprint("ui", __name__)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
LOG_PATTERN = re.compile(r"^(?P<ts>[^ ]+) \[(?P<level>[^\]]+)\] - \[(?P<event>[^\]]+)\] (?P<body>.*)$")


def _parse_kv_body(body):
    result = {}
    for chunk in body.split():
        if "=" in chunk:
            key, value = chunk.split("=", 1)
            result[key] = value.strip().strip(",")
    return result


def _load_log_lines():
    try:
        with open("logs.txt", "r", encoding="utf-8", errors="ignore") as file:
            return [line.strip() for line in file.readlines() if line.strip()]
    except FileNotFoundError:
        return []


def _build_dashboard_state():
    items = OrderedDict()
    lines = _load_log_lines()

    for line in lines:
        match = LOG_PATTERN.match(line)
        if not match:
            continue

        event = match.group("event")
        body = _parse_kv_body(match.group("body"))
        uetr = body.get("UETR") or body.get("uetr")
        # fallback: some log lines (scheduler messages) include the UETR as plain text
        # e.g. "Scheduled forward for <uetr> in 5s" — not key=value. Try to extract UUID-like token.
        if not uetr:
            m = re.search(r"\b[0-9a-fA-F\-]{36}\b", match.group("body"))
            if m:
                uetr = m.group(0)
                # also populate body so downstream looksups can use it
                body["UETR"] = uetr
        if not uetr:
            continue

        item = items.setdefault(
            uetr,
            {
                "uetr": uetr,
                "message_id": body.get("MSG", ""),
                "sender": body.get("SENDER", ""),
                "receiver": body.get("TO", body.get("RECEIVER_BIC", "")),
                "bank": body.get("BANK", ""),
                "amount": body.get("AMOUNT", ""),
                "currency": body.get("CURRENCY", ""),
                "phase": "incoming",
                "status": "received",
                "details": "",
                "timestamp": match.group("ts"),
                "pending": False,
            },
        )

        item["timestamp"] = match.group("ts")

        if event == "RECEIVED":
            item.update(
                {
                    "phase": "incoming",
                    "status": "received",
                    "message_id": body.get("MSG", item["message_id"]),
                    "sender": body.get("SENDER", item["sender"]),
                    "amount": body.get("AMOUNT", item["amount"]),
                    "currency": body.get("CURRENCY", item["currency"]),
                }
            )
        elif event == "ROUTED":
            item.update(
                {
                    "receiver": body.get("TO", item["receiver"]),
                    "bank": body.get("BANK", item["bank"]),
                }
            )
            # compute route when we get routing info
            try:
                route = get_route(body.get("FROM"), body.get("TO"))
                item["route"] = route
            except Exception:
                item["route"] = item.get("route", [])
        elif event == "SCHEDULER":
            text = match.group("body")
            if "Scheduled forward" in text:
                item.update({"phase": "pending", "status": "queued", "pending": True, "details": text})
            elif "Cancelled pending" in text:
                item.update({"phase": "completed", "status": "cancelled", "pending": False, "details": text})
            elif "Finished forward" in text:
                item.update({"phase": "completed", "status": "sent", "pending": False, "details": text})
            elif "[ERROR]" in text:
                item.update({"phase": "completed", "status": "error", "pending": False, "details": text})
        elif event == "COMPLETED":
            item.update({"phase": "completed", "status": "sent", "pending": False, "details": body.get("STATUS", "")})
        elif event == "VALIDATION_FAILED":
            item.update({"phase": "completed", "status": "error", "pending": False, "details": body.get("REASON", "validation_failed")})
        elif event == "ROUTING_FAILED":
            item.update({"phase": "completed", "status": "error", "pending": False, "details": body.get("REASON", "routing_failed")})

    incoming = []
    pending = []
    completed = []

    for item in items.values():
        base = {
            "uetr": item["uetr"],
            "message_id": item["message_id"],
            "sender": item["sender"],
            "receiver": item["receiver"],
            "bank": item["bank"],
            "amount": item["amount"],
            "currency": item["currency"],
            "status": item["status"],
            "details": item["details"],
            "route": item.get("route", []),
            "timestamp": item["timestamp"],
        }
        if item["phase"] == "incoming":
            incoming.append(base)
        elif item["phase"] == "pending":
            pending.append(base)
        else:
            completed.append(base)

    return {
        "incoming": list(reversed(incoming)),
        "pending": list(reversed(pending)),
        "completed": list(reversed(completed)),
        "metrics": {
            "incoming": len(incoming),
            "pending": len(pending),
            "completed": len(completed),
        },
    }


@ui_bp.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@ui_bp.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(FRONTEND_DIR, filename)


@ui_bp.route("/api/logs")
def api_logs():
    # return last 200 lines of logs.txt
    try:
        with open("logs.txt", "r") as f:
            lines = f.readlines()[-200:]
    except FileNotFoundError:
        lines = []
    return jsonify({"lines": [l.strip() for l in lines]})


@ui_bp.route("/api/pending")
def api_pending():
    return jsonify({"pending": scheduler.list_pending()})


@ui_bp.route("/api/dashboard")
def api_dashboard():
    return jsonify(_build_dashboard_state())


@ui_bp.route("/api/cancel/<uetr>", methods=["POST"])
def api_cancel(uetr):
    ok = scheduler.cancel_pending(uetr)
    if not ok:
        return jsonify({"error": "not_found_or_too_late"}), 404
    return jsonify({"status": "cancelled", "uetr": uetr}), 200



@ui_bp.route("/api/send/<uetr>", methods=["POST"])
def api_send(uetr):
    entry = inbox.pop_incoming(uetr)
    if not entry:
        return jsonify({"error": "not_found"}), 404

    message = entry.get("message")
    xml = entry.get("xml")
    scheduled = scheduler.schedule_forward(message, xml)
    return jsonify({"status": "scheduled", "uetr": uetr, "scheduled_in": scheduled.get("scheduled_in_secs")}), 202


@ui_bp.route("/api/token", methods=["POST"])
def api_token():
    # simple helper to fetch mock token for demo purposes
    client_id = request.form.get("client_id", "test-client")
    client_secret = request.form.get("client_secret", "test-secret")
    token = issue_token(client_id, client_secret)
    if not token:
        return jsonify({"error": "invalid_client"}), 401
    return jsonify(token)
