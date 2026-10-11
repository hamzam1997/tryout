import { useCallback, useEffect, useState } from "react";
import { createInvitation, listInvitations, revokeInvitation } from "../api";

// Owners and admins: invite by email and manage pending invites.
export default function InvitationsCard({ workspaceId }) {
  const [invitations, setInvitations] = useState([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [lastLink, setLastLink] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    listInvitations(workspaceId).then(setInvitations).catch((err) => setError(err.message));
  }, [workspaceId]);
  useEffect(load, [load]);

  async function handleInvite(event) {
    event.preventDefault();
    setError("");
    try {
      const invitation = await createInvitation(workspaceId, email.trim(), role);
      setLastLink(`${window.location.origin}/invite/${invitation.token}`);
      setEmail("");
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleRevoke(token) {
    await revokeInvitation(workspaceId, token).catch((err) => setError(err.message));
    load();
  }

  return (
    <section className="card report-section">
      <div className="card-head">
        <div>
          <h2>Invitations</h2>
          <p className="card-hint">Links are single use, work only for the invited email, and expire after 7 days.</p>
        </div>
      </div>
      <div className="card-body">
        {error && <div className="alert alert-error">{error}</div>}
        <form className="settings-form" onSubmit={handleInvite}>
          <div className="field">
            <label htmlFor="invite-email">Email</label>
            <input id="invite-email" className="input" type="email" required value={email}
              onChange={(event) => setEmail(event.target.value)} placeholder="teammate@company.com" />
          </div>
          <div className="field field-narrow">
            <label htmlFor="invite-role">Role</label>
            <select id="invite-role" className="input" value={role} onChange={(event) => setRole(event.target.value)}>
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <button type="submit" className="btn btn-primary">Create invite link</button>
        </form>
        {lastLink && (
          <p className="detail-note">
            Send this link: <input className="input invite-link" readOnly value={lastLink}
              onFocus={(event) => event.target.select()} aria-label="Invite link" />
          </p>
        )}
        {invitations.length > 0 && (
          <ul className="log-list invite-list">
            {invitations.map((invitation) => (
              <li key={invitation.token} className="log-item log-top">
                <strong>{invitation.email}</strong>
                <span className="log-owner">{invitation.role}</span>
                <span className="log-owner">expires {new Date(invitation.expires_at).toLocaleDateString()}</span>
                <button type="button" className="link-btn" onClick={() => handleRevoke(invitation.token)}>
                  Revoke
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
