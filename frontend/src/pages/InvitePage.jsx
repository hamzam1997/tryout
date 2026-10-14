import { useEffect, useState } from "react";
import { acceptInvitation, getInvitation } from "../api";
import LoadingRows from "../components/LoadingRows";

// Reached from an invite link; the user is already signed in (App shows login first).
export default function InvitePage({ token }) {
  const [invitation, setInvitation] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getInvitation(token).then(setInvitation).catch((err) => setError(err.message));
  }, [token]);

  async function handleAccept() {
    setBusy(true);
    try {
      await acceptInvitation(token);
      window.location.assign("/repositories"); // reload into the joined workspace
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="container">
      <header className="page-head">
        <div>
          <p className="page-kicker">Invitation</p>
          <h1>{invitation ? `Join ${invitation.workspace.name}` : "Workspace invitation"}</h1>
          {invitation && <p className="page-sub">Someone on {invitation.workspace.name} invited you to collaborate.</p>}
        </div>
      </header>
      {error && <div className="alert alert-error">{error}</div>}
      {!invitation && !error && <LoadingRows label="Checking invitation…" />}
      {invitation && (
        <section className="card invite-card">
          <div className="card-body invite-body">
            <span className="workspace-initial is-lg" aria-hidden="true">
              {invitation.workspace.name[0].toUpperCase()}
            </span>
            <div className="invite-text">
              <strong>{invitation.workspace.name}</strong>
              <span className="card-hint">You'll join as {invitation.role} and see its repositories, meetings and ideas.</span>
            </div>
            <button type="button" className="btn btn-primary" disabled={busy} onClick={handleAccept}>
              {busy ? "Joining…" : "Join workspace"}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
