import { useEffect, useState } from "react";
import { deleteWorkspace, listWorkspaces, renameWorkspace } from "../api";
import GitHubCard from "../components/GitHubCard";
import InvitationsCard from "../components/InvitationsCard";
import LoadingRows from "../components/LoadingRows";
import MembersCard from "../components/MembersCard";

export default function SettingsPage() {
  const [workspace, setWorkspace] = useState(null);
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    listWorkspaces()
      .then((data) => {
        const current = data.workspaces.find((ws) => ws.id === data.current);
        setWorkspace(current);
        setName(current?.name || "");
      })
      .catch((err) => setError(err.message));
  }, []);

  const isOwner = workspace?.role === "owner";

  async function handleRename(event) {
    event.preventDefault();
    setError("");
    try {
      await renameWorkspace(workspace.id, name.trim());
      setMessage("Saved.");
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete() {
    const typed = window.prompt(`This deletes every repository, meeting, idea and attempt in "${workspace.name}". Type its name to confirm.`);
    if (typed !== workspace.name) return;
    try {
      await deleteWorkspace(workspace.id);
      window.location.assign("/repositories");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="container">
      <header className="page-head">
        <div>
          <p className="page-kicker">Workspace</p>
          <h1>Settings</h1>
        </div>
      </header>

      {error && <div className="alert alert-error">{error}</div>}
      {!workspace && !error && <LoadingRows label="Loading workspace…" />}

      {workspace && (
        <>
          <section className="card report-section">
            <div className="card-head">
              <div>
                <h2>General</h2>
                <p className="card-hint">Your role: {workspace.role}</p>
              </div>
            </div>
            <form className="card-body settings-form" onSubmit={handleRename}>
              <div className="field">
                <label htmlFor="workspace-name">Workspace name</label>
                <input
                  id="workspace-name"
                  className="input"
                  value={name}
                  maxLength={80}
                  disabled={!isOwner}
                  onChange={(event) => {
                    setName(event.target.value);
                    setMessage("");
                  }}
                />
              </div>
              {isOwner && (
                <button type="submit" className="btn btn-primary" disabled={!name.trim() || name === workspace.name}>
                  Save
                </button>
              )}
              {message && <span className="detail-note is-ok">{message}</span>}
            </form>
          </section>

          <MembersCard workspaceId={workspace.id} myRole={workspace.role} />

          {(isOwner || workspace.role === "admin") && <InvitationsCard workspaceId={workspace.id} />}

          <GitHubCard workspaceId={workspace.id} canManage={isOwner || workspace.role === "admin"} />

          {isOwner && (
            <section className="card report-section">
              <div className="card-head">
                <div>
                  <h2>Danger zone</h2>
                  <p className="card-hint">Deleting a workspace removes all of its data for every member.</p>
                </div>
              </div>
              <div className="card-body">
                <button type="button" className="btn btn-secondary btn-danger" onClick={handleDelete}>
                  Delete workspace
                </button>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
