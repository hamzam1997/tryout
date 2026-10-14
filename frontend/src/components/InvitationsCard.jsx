import { useCallback, useEffect, useState } from "react";
import { createInvitation, listInvitations, revokeInvitation } from "../api";
import { formatDate } from "../lib/format";
import { Avatar } from "./Icon";

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
          <div className="field invite-link-field">
            <label htmlFor="invite-link">Send this link to your teammate</label>
            <input id="invite-link" className="input invite-link" readOnly value={lastLink}
              onFocus={(event) => event.target.select()} />
          </div>
        )}
        {invitations.length > 0 && (
          <ul className="member-list invite-list">
            {invitations.map((invitation) => (
              <li key={invitation.token} className="member-row">
                <Avatar name={invitation.email} size={32} />
                <span className="member-id">
                  <strong>{invitation.email}</strong>
                  <span className="member-email">Pending · expires {formatDate(invitation.expires_at)}</span>
                </span>
                <span className="badge badge-idle role-badge">{invitation.role}</span>
                <button type="button" className="btn btn-ghost btn-sm btn-danger" onClick={() => handleRevoke(invitation.token)}>
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
