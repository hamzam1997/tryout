from flask import Flask, request
import contextvars
import threading
import time

app = Flask(__name__)

def background():
    time.sleep(1)
    try:
        print("Background host URL:", request.host_url)
    except Exception as e:
        print("Background exception:", e)

@app.route("/")
def index():
    t = threading.Thread(
        target=contextvars.copy_context().run,
        args=(background,),
    )
    t.start()
    return "OK"

with app.test_request_context("/"):
    index()

time.sleep(2)
