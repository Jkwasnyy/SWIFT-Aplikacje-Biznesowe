from flask import Blueprint, request, jsonify
from app.services.swift_service import handle_swift_message
from app.core.auth import issue_token, validate_token
from app.services.scheduler import cancel_pending

swift_bp = Blueprint("swift", __name__)


@swift_bp.route("/auth/token", methods=["POST"])  # mock token endpoint
def token():
    client_id = request.form.get("client_id")
    client_secret = request.form.get("client_secret")
    token = issue_token(client_id, client_secret)
    if not token:
        return jsonify({"error": "invalid_client"}), 401
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