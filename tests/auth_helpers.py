"""Sign a Flask test client in, the way a verified firebase-sync would."""

import database as db


def login(client, uid="test-user", email="test@example.com", name="Test User"):
    """Signed-in user with their own workspace; records the test creates land in it."""
    workspace = db.create_workspace(f"{name}'s workspace", uid)
    db.set_workspace(workspace.id)
    with client.session_transaction() as sess:
        sess["user"] = {"uid": uid, "email": email, "name": name}
        sess["workspace_id"] = workspace.id
    return client
