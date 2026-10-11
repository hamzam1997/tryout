import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

import database as db
from app import app
from auth_helpers import login
from database.documents import utc_now
from schemas import WorkspaceRole


def signed_in(uid, email, verified=True):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = {"uid": uid, "email": email, "email_verified": verified}
    return client


class TestInvitations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self.tmp.name) / "database")
        db.init_db()
        self.owner = login(app.test_client(), uid="owner")
        self.ws = db.current_workspace()

    def tearDown(self):
        db.set_database_path(None)
        self.tmp.cleanup()

    def _invite(self, email="b@x.com", role="member", client=None):
        return (client or self.owner).post(
            f"/api/workspaces/{self.ws}/invitations", json={"email": email, "role": role}
        )

    def test_invitee_accepts_and_joins_with_the_role(self):
        token = self._invite(email="B@x.com", role="admin").get_json()["token"]
        b = signed_in("b", "b@x.com")
        self.assertEqual(b.get(f"/api/invitations/{token}").get_json()["workspace"]["id"], self.ws)
        self.assertEqual(b.post(f"/api/invitations/{token}/accept").status_code, 200)
        self.assertEqual(db.get_membership(self.ws, "b").role, WorkspaceRole.ADMIN)
        self.assertEqual(self.owner.get(f"/api/workspaces/{self.ws}/invitations").get_json(), [])

    def test_link_is_single_use_and_bound_to_the_email(self):
        token = self._invite().get_json()["token"]
        self.assertEqual(signed_in("c", "c@x.com").post(f"/api/invitations/{token}/accept").status_code, 403)
        self.assertEqual(signed_in("b", "b@x.com", verified=False).post(f"/api/invitations/{token}/accept").status_code, 403)
        self.assertEqual(signed_in("b", "b@x.com").post(f"/api/invitations/{token}/accept").status_code, 200)
        self.assertEqual(signed_in("b2", "b@x.com").post(f"/api/invitations/{token}/accept").status_code, 404)

    def test_expired_and_revoked_links_fail(self):
        expired = db.create_invitation(self.ws, "b@x.com", WorkspaceRole.MEMBER, "owner")
        expired.expires_at = utc_now() - timedelta(seconds=1)
        db.save_invitation(expired)
        self.assertEqual(signed_in("b", "b@x.com").post(f"/api/invitations/{expired.token}/accept").status_code, 404)

        token = self._invite().get_json()["token"]
        self.assertEqual(self.owner.delete(f"/api/workspaces/{self.ws}/invitations/{token}").status_code, 204)
        self.assertEqual(signed_in("b", "b@x.com").post(f"/api/invitations/{token}/accept").status_code, 404)

    def test_only_owners_and_admins_invite_and_never_as_owner(self):
        db.add_member(self.ws, "m", WorkspaceRole.MEMBER)
        member = signed_in("m", "m@x.com")
        self.assertEqual(self._invite(client=member).status_code, 403)
        self.assertEqual(self._invite(role="owner").status_code, 400)
        self.assertEqual(self._invite(email="not-an-email").status_code, 400)

    def test_revoking_another_workspaces_invite_is_404(self):
        other = db.create_workspace("Other", "someone")
        theirs = db.create_invitation(other.id, "b@x.com", WorkspaceRole.MEMBER, "someone")
        self.assertEqual(self.owner.delete(f"/api/workspaces/{self.ws}/invitations/{theirs.token}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
