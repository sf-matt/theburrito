import os

from flask import Flask, jsonify


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)

    @app.get("/")
    def index():
        return jsonify(message=os.getenv("APP_MESSAGE", "Hello from CloudSecBurrito!"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
