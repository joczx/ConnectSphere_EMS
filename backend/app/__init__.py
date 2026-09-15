from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from app.routes.events import events


def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.register_blueprint(events)

    # Allow requests from the React frontend
    CORS(app, origins=["http://localhost:5173"])

    @app.route("/")
    def home():
        return {
            "message": "ConnectSphere Flask API is running!"
        }

    return app
