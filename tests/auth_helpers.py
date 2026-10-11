"""Sign a Flask test client in, the way a verified firebase-sync would."""


def login(client, uid="test-user", email="test@example.com", name="Test User"):
    with client.session_transaction() as sess:
        sess["user"] = {"uid": uid, "email": email, "name": name}
    return client
