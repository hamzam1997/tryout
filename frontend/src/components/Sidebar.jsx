const ICONS = {
  repositories: (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5v-9zm10.5-1h-8a1 1 0 0 0-1 1v6.7c.28-.13.59-.2.928-.2h8.072V1.5z" />
    </svg>
  ),
  meetings: (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <rect x="2.25" y="3.25" width="11.5" height="10.5" rx="1.5" />
      <path d="M2.25 6.5h11.5M5.5 1.75v3M10.5 1.75v3" />
    </svg>
  ),
  ideas: (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 1.75a4.25 4.25 0 0 0-2.5 7.7v1.3h5v-1.3A4.25 4.25 0 0 0 8 1.75Z" />
      <path d="M6.5 13.25h3" />
    </svg>
  ),
};

const NAV = [
  { id: "repositories", label: "Repositories" },
  { id: "meetings", label: "Meetings" },
  { id: "ideas", label: "Ideas" },
];

export default function Sidebar({ view, onNavigate, counts, online }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">t</span>
        <div className="brand-text">
          <span className="brand-name">tryout</span>
          <span className="brand-tag">Future of work prototype</span>
          <div className="brand-flow" aria-hidden="true">
            <span>Repo</span>
            <span>Meeting</span>
            <span>Idea</span>
            <span>Attempt</span>
          </div>
        </div>
      </div>

      <nav className="nav">
        <p className="nav-label">Workspace</p>
        {NAV.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            className="nav-item"
            aria-current={view === id ? "page" : undefined}
            onClick={() => onNavigate(id)}
          >
            {ICONS[id]}
            {label}
            {counts[id] > 0 && (
              <span className={`nav-count${id === "ideas" ? " is-alert" : ""}`}>
                {counts[id]}
              </span>
            )}
          </button>
        ))}
      </nav>

      <div className="sidebar-foot">
        <span
          className={`dot ${online === null ? "" : online ? "is-up" : "is-down"}`}
        />
        <span>
          {online === null ? "Connecting…" : online ? "API connected" : "API unreachable"}
        </span>
      </div>
    </aside>
  );
}
