import { useEffect, useState } from "react";
import { createWorkspace, listWorkspaces, switchWorkspace } from "../api";

// A full reload after switching guarantees no page keeps the old workspace's data.
const reloadInto = () => window.location.assign("/repositories");

export default function WorkspaceSwitcher({ onOpenSettings }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    listWorkspaces().then(setData).catch(() => {});
  }, []);

  async function handleChange(event) {
    const value = event.target.value;
    if (value === "new") {
      const name = window.prompt("Name the new workspace");
      if (name?.trim()) {
        await createWorkspace(name.trim());
        reloadInto();
      }
      return;
    }
    await switchWorkspace(Number(value));
    reloadInto();
  }

  if (!data) return null;
  return (
    <div className="workspace-switcher">
      <label className="nav-label" htmlFor="workspace-select">Workspace</label>
      <select id="workspace-select" className="input" value={data.current} onChange={handleChange}>
        {data.workspaces.map((ws) => (
          <option key={ws.id} value={ws.id}>
            {ws.name}
          </option>
        ))}
        <option value="new">+ New workspace…</option>
      </select>
      <button type="button" className="link-btn" onClick={onOpenSettings}>
        Workspace settings
      </button>
    </div>
  );
}
