from flask import Blueprint, request, jsonify
from app.services.swift_service import handle_swift_message
from app.services.parser import parse_xml
from app.core.auth import issue_token, validate_token, get_token_claims
from app.services.scheduler import cancel_pending
from app.core.logger import log

swift_bp = Blueprint("swift", __name__)


@swift_bp.route("/auth/token", methods=["POST"])  # mock token endpoint
def token():
    # Support OAuth2 client_credentials grant
    grant = request.form.get("grant_type", "client_credentials")
    client_id = request.form.get("client_id")
    client_secret = request.form.get("client_secret")

    # Also accept basic auth: Authorization: Basic base64(client:secret)
    if not client_id:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            import base64

            try:
                decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
                parts = decoded.split(":", 1)
                client_id = parts[0]
                client_secret = parts[1] if len(parts) > 1 else None
            except Exception:
                client_id = None

    if grant != "client_credentials":
        return jsonify({"error": "unsupported_grant_type"}), 400

    token = issue_token(client_id, client_secret)
    if not token:
        return jsonify({"error": "invalid_client"}), 401
    # Normalize token_type
    token["token_type"] = token.get("token_type", "bearer").capitalize()
    return jsonify(token), 200


def _require_auth(req):
    """Return token claims dict when auth ok, else False.

    This allows callers to inspect claims (e.g. allowed `banks`).
    """
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth.split(" ", 1)[1]
    if not validate_token(token):
        return False
    return get_token_claims(token) or {}


@swift_bp.route("/swift/message", methods=["POST"])
def receive_message():
    claims = _require_auth(request)
    if not claims:
        return jsonify({"error": "unauthorized"}), 401

    xml_data = request.data.decode("utf-8")
    try:
        parsed = parse_xml(xml_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    allowed_banks = set(claims.get("banks", []))
    sender_bic = getattr(parsed, "sender_bic", "")
    if allowed_banks and sender_bic and sender_bic not in allowed_banks:
        return jsonify({"error": "forbidden_sender_bic"}), 403

    result, status = handle_swift_message(xml_data)
    return jsonify(result), status


@swift_bp.route("/swift/cancel/<uetr>", methods=["POST"])
def cancel(uetr):
    claims = _require_auth(request)
    if not claims:
        return jsonify({"error": "unauthorized"}), 401

    # try to find pending entry and ensure caller is allowed to cancel for that sender
    pending = None
    try:
        for entry in __import__("app.services.scheduler", fromlist=["list_pending"]).list_pending():
            if entry.get("uetr") == uetr:
                pending = entry
                break
    except Exception:
        pending = None

    if pending:
        allowed_banks = set(claims.get("banks", []))
        sender_bic = pending.get("from")
        if allowed_banks and sender_bic and sender_bic not in allowed_banks:
            return jsonify({"error": "forbidden"}), 403

    ok = cancel_pending(uetr)
    if not ok:
        return jsonify({"error": "not_found_or_too_late"}), 404
    return jsonify({"status": "cancelled", "uetr": uetr}), 200


@swift_bp.route("/api/bank/ack", methods=["POST"])
def bank_ack():
    payload = request.get_json(silent=True) or {}
    uetr = payload.get("uetr", "")
    message_id = payload.get("message_id", "")
    bank = payload.get("bank", "")
    received_at = payload.get("received_at", "")

    log(
        f"[COMPLETED] MSG={message_id} UETR={uetr} BANK={bank} RECEIVED_AT={received_at} STATUS=completed"
    )
    return jsonify({"status": "ok", "uetr": uetr}), 200
