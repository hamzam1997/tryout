import { useCallback, useEffect, useState } from "react";
import { changeMemberRole, listMembers, removeMember } from "../api";
import { formatDate } from "../lib/format";

const ROLES = ["owner", "admin", "member"];

// Everyone sees the list; owners and admins change roles and remove people.
// The server enforces the rules (e.g. the last owner); this just shows its errors.
export default function MembersCard({ workspaceId, myRole }) {
  const [members, setMembers] = useState([]);
  const [error, setError] = useState("");
  const canManage = myRole === "owner" || myRole === "admin";

  const load = useCallback(() => {
    listMembers(workspaceId).then(setMembers).catch((err) => setError(err.message));
  }, [workspaceId]);
  useEffect(load, [load]);

  async function run(action) {
    setError("");
    try {
      await action();
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleLeave(uid) {
    if (!window.confirm("Leave this workspace? You will lose access to its data.")) return;
    try {
      await removeMember(workspaceId, uid);
      window.location.assign("/repositories");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="card report-section">
      <div className="card-head">
        <div>
          <h2>Members</h2>
          <p className="card-hint">Members approve ideas and run attempts. Admins also manage repositories, meetings and people.</p>
        </div>
      </div>
      <div className="card-body">
        {error && <div className="alert alert-error">{error}</div>}
        <ul className="log-list">
          {members.map((member) => (
            <li key={member.uid} className="log-item log-top">
              <strong>{member.name}{member.you ? " (you)" : ""}</strong>
              {member.email && <span className="log-owner">{member.email}</span>}
              <span className="log-owner">joined {formatDate(member.joined_at)}</span>
              {canManage && !member.you ? (
                <select
                  className="input member-role"
                  aria-label={`Role for ${member.name}`}
                  value={member.role}
                  onChange={(event) => run(() => changeMemberRole(workspaceId, member.uid, event.target.value))}
                >
                  {ROLES.map((role) => <option key={role} value={role}>{role}</option>)}
                </select>
              ) : (
                <span className="badge badge-idle">{member.role}</span>
              )}
              {member.you ? (
                <button type="button" className="link-btn" onClick={() => handleLeave(member.uid)}>Leave</button>
              ) : (
                canManage && (
                  <button type="button" className="link-btn" onClick={() => run(() => removeMember(workspaceId, member.uid))}>
                    Remove
                  </button>
                )
              )}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
