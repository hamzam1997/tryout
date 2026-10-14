import { useEffect, useState } from "react";
import { createWorkspace, listWorkspaces, switchWorkspace } from "../api";
import Icon from "./Icon";

// A full reload after switching guarantees no page keeps the old workspace's data.
const reloadInto = () => window.location.assign("/repositories");

export default function WorkspaceSwitcher() {
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

  if (!data) return <div className="workspace-switcher is-loading" aria-hidden="true" />;
  const current = data.workspaces.find((ws) => ws.id === data.current);
  return (
    <label className="workspace-switcher">
      <span className="workspace-initial" aria-hidden="true">
        {(current?.name || "W")[0].toUpperCase()}
      </span>
      <span className="workspace-text">
        <span className="workspace-label">Workspace</span>
        <span className="workspace-name">{current?.name || "Workspace"}</span>
      </span>
      <Icon name="chevronDown" className="workspace-chevron" />
      <select aria-label="Switch workspace" value={data.current} onChange={handleChange}>
        {data.workspaces.map((ws) => (
          <option key={ws.id} value={ws.id}>
            {ws.name}
          </option>
        ))}
        <option value="new">+ New workspace…</option>
      </select>
    </label>
  );
}
