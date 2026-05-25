from flask import Blueprint, request, jsonify
from app.services.swift_service import handle_swift_message
from app.core.auth import issue_token, validate_token
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
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth.split(" ", 1)[1]
    return validate_token(token)


@swift_bp.route("/swift/message", methods=["POST"])
def receive_message():
    if not _require_auth(request):
        return jsonify({"error": "unauthorized"}), 401

    xml_data = request.data.decode("utf-8")
    result, status = handle_swift_message(xml_data)
    return jsonify(result), status


@swift_bp.route("/swift/cancel/<uetr>", methods=["POST"])
def cancel(uetr):
    if not _require_auth(request):
        return jsonify({"error": "unauthorized"}), 401

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
