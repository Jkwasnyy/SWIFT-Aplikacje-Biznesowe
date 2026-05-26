from flask import Flask
import os
from app.api.routes import swift_bp
from app.api.ui import ui_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(swift_bp)
    app.register_blueprint(ui_bp)
    return app

if __name__ == "__main__":
    app = create_app()
    bind_host = os.getenv("APP_BIND_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "3000"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host=bind_host, port=port, debug=debug)