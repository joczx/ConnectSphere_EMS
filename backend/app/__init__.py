import os

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from app.routes.events import events
from app.routes.equipment import equipment
from app.routes.venues import venues

# Read backend/.env before anything asks for a credential.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from app.routes.equipment_requests import bp as equipment_requests_bp  # noqa: E402
from app.routes.event_requests import event_requests_bp  # noqa: E402
from app.routes.login import login_bp  # noqa: E402
from app.routes.notifications import notifications_bp  # noqa: E402


def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.register_blueprint(events)
    app.register_blueprint(equipment)
    app.register_blueprint(venues)

    # Allow requests from the React frontend
    CORS(app, origins=["http://localhost:5173"])

    app.register_blueprint(login_bp)
    app.register_blueprint(equipment_requests_bp)
    app.register_blueprint(event_requests_bp)
    app.register_blueprint(notifications_bp)

    @app.route("/")
    def home():
        return {
            "message": "ConnectSphere Flask API is running!"
        }

    return app
