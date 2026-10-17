import { useCallback, useEffect, useState } from "react";
import { disconnectWorkspaceGitHub, getGithubAuthStatus, getWorkspaceGitHub } from "../api";
import { formatDate } from "../lib/format";

// One GitHub connection per workspace, so PRs work no matter who approves.
export default function GitHubCard({ workspaceId, canManage }) {
  const [status, setStatus] = useState(null);
  // The signed-in user's own GitHub login; PRs fall back to it when the workspace has none.
  const [personal, setPersonal] = useState(null);
  // The connect redirect comes back here with ?auth_error= when it fails.
  const [error, setError] = useState(() => new URLSearchParams(window.location.search).get("auth_error") || "");

  const load = useCallback(() => {
    getWorkspaceGitHub(workspaceId).then(setStatus).catch((err) => setError(err.message));
  }, [workspaceId]);
  useEffect(load, [load]);
  useEffect(() => {
    getGithubAuthStatus().then((s) => setPersonal(s.authenticated ? s.user : null)).catch(() => {});
  }, []);

  async function run(action) {
    setError("");
    try {
      await action();
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="card report-section">
      <div className="card-head">
        <div>
          <h2>GitHub</h2>
          <p className="card-hint">Onboarding and attempt pull requests use this connection for every member.</p>
        </div>
      </div>
      <div className="card-body settings-form">
        {error && <div className="alert alert-error">{error}</div>}
        {status?.connected ? (
          <>
            <span className="connection-status">
              <span className="dot is-up" />
              Connected as <strong>{status.login}</strong> since {formatDate(status.connected_at)}
            </span>
            {canManage && (
              <button type="button" className="btn btn-secondary" onClick={() => run(() => disconnectWorkspaceGitHub(workspaceId))}>
                Disconnect
              </button>
            )}
          </>
        ) : personal?.login ? (
          <>
            <span className="connection-status">
              <span className="dot is-up" />
              Connected as <strong>{personal.login}</strong> (your account). Connect the workspace to use it for every member.
            </span>
            {canManage && (
              <a className="btn btn-primary" href={`/api/auth/github/login?workspace=${workspaceId}`}>
                Connect GitHub
              </a>
            )}
          </>
        ) : (
          <>
            <span className="connection-status">
              <span className="dot" />
              Not connected. Connect GitHub to onboard private repositories and open pull requests.
            </span>
            {canManage && (
              <>
                <a className="btn btn-primary" href={`/api/auth/github/login?workspace=${workspaceId}`}>
                  Connect GitHub
                </a>
              </>
            )}
          </>
        )}
      </div>
    </section>
  );
}
