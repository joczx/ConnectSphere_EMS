from flask import Flask
from flask_cors import CORS


def create_app():
    app = Flask(__name__)

    # Allow requests from the React frontend
    CORS(app, origins=["http://localhost:5173"])

    @app.route("/")
    def home():
        return {
            "message": "ConnectSphere Flask API is running!"
        }

    return app