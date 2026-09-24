from flask import Flask

from config import settings
from database import init_db
from logging_setup import configure_logging
from views.meetings import bp as meetings_bp

configure_logging()

app = Flask(__name__)
init_db()
app.register_blueprint(meetings_bp)


@app.route("/")
def index():
    return "tryout is alive"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.port, debug=settings.debug)
