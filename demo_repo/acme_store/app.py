import os

from flask import Flask, jsonify

from routes.checkout import bp as checkout_bp
from routes.orders import bp as orders_bp
from routes.refunds import bp as refunds_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(orders_bp)
    app.register_blueprint(checkout_bp)
    app.register_blueprint(refunds_bp)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "service": "acme-store"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
