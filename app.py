from flask import Flask

from config import settings

app = Flask(__name__)


@app.route("/")
def index():
    return "tryout is alive"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.port, debug=settings.debug)
