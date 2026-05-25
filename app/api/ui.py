from flask import Blueprint, send_from_directory, jsonify, request
import os
import re
from collections import OrderedDict
from app.services import scheduler
from app.services import inbox
from app.core.auth import issue_token
from app.services.scheduler import schedule_forward

ui_bp = Blueprint("ui", __name__)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
LOG_PATTERN = re.compile(r"^(?P<ts>[^ ]+) \[(?P<level>[^\]]+)\] - \[(?P<event>[^\]]+)\] (?P<body>.*)$")


def _build_openapi_spec(base_url="/"):
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "SWIFT Middleware API",
            "version": "1.0.0",
            "description": "Mock SWIFT transfer flow with routing, fee split and operator dashboard.",
        },
        "servers": [{"url": base_url}],
        "tags": [
            {"name": "Auth", "description": "Token issuance"},
            {"name": "Swift", "description": "Transfer and cancellation endpoints"},
            {"name": "Dashboard", "description": "Operator data endpoints"},
            {"name": "Logs", "description": "Log inspection"},
        ],
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            }
        },
        "paths": {
            "/auth/token": {
                "post": {
                    "tags": ["Auth"],
                    "summary": "Issue mock access token",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/x-www-form-urlencoded": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "client_id": {"type": "string", "example": "test-client"},
                                        "client_secret": {"type": "string", "example": "test-secret"},
                                    },
                                    "required": ["client_id", "client_secret"],
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "Token issued"}, "401": {"description": "Invalid client"}},
                }
            },
            "/swift/message": {
                "post": {
                    "tags": ["Swift"],
                    "summary": "Submit SWIFT message",
                    "security": [{"bearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/xml": {
                                "schema": {"type": "string"},
                                "example": "<Document>...</Document>",
                            }
                        },
                    },
                    "responses": {
                        "202": {"description": "Accepted"},
                        "400": {"description": "Validation error"},
                        "401": {"description": "Unauthorized"},
                        "404": {"description": "Unknown bank or route"},
                        "422": {"description": "Closed receiver account"},
                    },
                }
            },
            "/swift/cancel/{uetr}": {
                "post": {
                    "tags": ["Swift"],
                    "summary": "Cancel pending transfer",
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {
                            "name": "uetr",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Transfer UETR",
                        }
                    ],
                    "responses": {
                        "200": {"description": "Cancelled"},
                        "401": {"description": "Unauthorized"},
                        "404": {"description": "Too late or not found"},
                    },
                }
            },
            "/api/dashboard": {
                "get": {"tags": ["Dashboard"], "summary": "Get dashboard state", "responses": {"200": {"description": "OK"}}}
            },
            "/api/pending": {
                "get": {"tags": ["Dashboard"], "summary": "List pending jobs", "responses": {"200": {"description": "OK"}}}
            },
            "/api/logs": {
                "get": {"tags": ["Logs"], "summary": "Get recent log lines", "responses": {"200": {"description": "OK"}}}
            },
            "/api/token": {
                "post": {"tags": ["Auth"], "summary": "Issue helper token for the UI", "responses": {"200": {"description": "OK"}, "401": {"description": "Invalid client"}}}
            },
            "/api/send/{uetr}": {
                "post": {
                    "tags": ["Dashboard"],
                    "summary": "Schedule a queued transfer",
                    "parameters": [
                        {"name": "uetr", "in": "path", "required": True, "schema": {"type": "string"}}
                    ],
                    "responses": {"202": {"description": "Scheduled"}, "404": {"description": "Not found"}, "422": {"description": "Account rejected"}},
                }
            },
            "/api/cancel/{uetr}": {
                "post": {
                    "tags": ["Dashboard"],
                    "summary": "Cancel queued transfer from the UI",
                    "parameters": [
                        {"name": "uetr", "in": "path", "required": True, "schema": {"type": "string"}}
                    ],
                    "responses": {"200": {"description": "Cancelled"}, "404": {"description": "Not found"}},
                }
            },
        },
    }


def _build_docs_html():
    return """<!doctype html>
<html lang="pl">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>SWIFT API Docs</title>
        <link rel="stylesheet" href="/assets/style.css" />
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
    <style>
            body { min-height: 100vh; }
            .docs-shell { padding: 24px; display: grid; gap: 18px; grid-template-columns: 360px minmax(0, 1fr); }
            .docs-panel { padding: 18px; }
            .docs-panel h1, .docs-panel h2, .docs-panel h3, .docs-panel p { margin-top: 0; }
            .docs-panel p, .docs-panel li { color: var(--muted); }
            .docs-list { margin: 12px 0 0; padding-left: 20px; }
            .docs-list li { margin-bottom: 10px; }
            #swagger-ui { background: rgba(15, 23, 42, 0.2); border-radius: 20px; padding: 10px; }
            .docs-badge { display: inline-block; margin-bottom: 12px; padding: 6px 10px; border-radius: 999px; background: rgba(96, 165, 250, 0.16); color: #dbeafe; font-weight: 700; }
            @media (max-width: 1100px) { .docs-shell { grid-template-columns: 1fr; } }
    </style>
  </head>
  <body>
        <div class="docs-shell">
            <aside class="card docs-panel">
                <div class="docs-badge">Swagger UI</div>
                <h1>API po kolei</h1>
                <p>Najpierw logowanie, potem wysyłka przelewu, a dalej kontrola kolejki i logów.</p>
                <ol class="docs-list">
                    <li><strong>POST</strong> /auth/token</li>
                    <li><strong>POST</strong> /swift/message</li>
                    <li><strong>POST</strong> /swift/cancel/{uetr}</li>
                    <li><strong>GET</strong> /api/dashboard</li>
                    <li><strong>GET</strong> /api/pending</li>
                    <li><strong>GET</strong> /api/logs</li>
                    <li><strong>POST</strong> /api/send/{uetr}</li>
                    <li><strong>POST</strong> /api/cancel/{uetr}</li>
                </ol>
                <p>Pełny opis i możliwość testowania parametrów jest po prawej.</p>
            </aside>
            <main class="card docs-panel">
                <div id="swagger-ui"></div>
            </main>
        </div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
    <script>
      window.onload = function () {
        window.ui = SwaggerUIBundle({
          url: "/api/openapi.json",
          dom_id: "#swagger-ui",
          deepLinking: true,
          presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
          layout: "BaseLayout",
                    docExpansion: "list",
          operationsSorter: "alpha",
          tagsSorter: "alpha",
          validatorUrl: null,
        });
      };
    </script>
  </body>
</html>"""


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
                "route": [],
                "eta_seconds": "",
                "fee_total": "",
                "fee_split": "",
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
            route_text = body.get("ROUTE", "")
            item.update(
                {
                    "receiver": body.get("TO", item["receiver"]),
                    "bank": body.get("BANK", item["bank"]),
                    "route": route_text.split(">") if route_text else item.get("route", []),
                    "eta_seconds": body.get("ETA_SECONDS", item.get("eta_seconds", "")),
                    "fee_total": body.get("FEE_TOTAL", item.get("fee_total", "")),
                    "fee_split": body.get("FEE_SPLIT", item.get("fee_split", "")),
                }
            )
        elif event == "SCHEDULER":
            text = match.group("body")
            if "Scheduled forward" in text:
                item.update({"phase": "pending", "status": "queued", "pending": True, "details": text})
            elif "Cancelled pending" in text:
                item.update({"phase": "completed", "status": "cancelled", "pending": False, "details": text})
            elif "Finished forward" in text:
                item.update({"phase": "completed", "status": "completed", "pending": False, "details": text})
            elif "[ERROR]" in text:
                item.update({"phase": "completed", "status": "error", "pending": False, "details": text})
        elif event == "COMPLETED":
            item.update({"phase": "completed", "status": "completed", "pending": False, "details": body.get("STATUS", "")})
        elif event == "VALIDATION_FAILED":
            item.update({"phase": "completed", "status": "error", "pending": False, "details": body.get("REASON", "validation_failed")})
        elif event == "ROUTING_FAILED":
            item.update({"phase": "completed", "status": "error", "pending": False, "details": body.get("REASON", "routing_failed")})
        elif event == "SETTLEMENT_FAILED":
            item.update({"phase": "completed", "status": "error", "pending": False, "details": body.get("REASON", "settlement_failed")})

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
            "eta_seconds": item.get("eta_seconds", ""),
            "fee_total": item.get("fee_total", ""),
            "fee_split": item.get("fee_split", ""),
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


@ui_bp.route("/api/openapi.json")
def api_openapi_json():
    return jsonify(_build_openapi_spec(base_url=request.host_url.rstrip("/")))


@ui_bp.route("/docs")
def docs():
    return _build_docs_html()


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
    entry = inbox.get_incoming(uetr)
    if not entry:
        return jsonify({"error": "not_found"}), 404

    message = entry.get("message")
    xml = entry.get("xml")
    scheduled = schedule_forward(
        message,
        xml,
        metadata={
            "route": entry.get("route", []),
            "fee_breakdown": entry.get("fee_breakdown", {}),
            "estimated_seconds": entry.get("estimated_seconds", 0.0),
        },
    )
    if scheduled.get("error"):
        return jsonify({"error": scheduled["error"], "uetr": uetr}), 422

    inbox.pop_incoming(uetr)
    return jsonify(
        {
            "status": "scheduled",
            "uetr": uetr,
            "scheduled_in": scheduled.get("scheduled_in_secs"),
            "route": entry.get("route", []),
            "fee_breakdown": entry.get("fee_breakdown", {}),
        }
    ), 202


@ui_bp.route("/api/token", methods=["POST"])
def api_token():
    # simple helper to fetch mock token for demo purposes
    client_id = request.form.get("client_id", "test-client")
    client_secret = request.form.get("client_secret", "test-secret")
    token = issue_token(client_id, client_secret)
    if not token:
        return jsonify({"error": "invalid_client"}), 401
    return jsonify(token)
