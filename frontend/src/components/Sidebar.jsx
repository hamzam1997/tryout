const ICONS = {
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
  { id: "meetings", label: "Meetings" },
  { id: "ideas", label: "Ideas" },
];

export default function Sidebar({ view, onNavigate, counts, online }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">t</span>
        <span className="brand-name">tryout</span>
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
            {counts[id] > 0 && <span className="nav-count">{counts[id]}</span>}
          </button>
        ))}
      </nav>

      <div className="sidebar-foot">
        <span className={`dot ${online === null ? "" : online ? "is-up" : "is-down"}`} />
        {online === null ? "Connecting…" : online ? "API connected" : "API unreachable"}
      </div>
    </aside>
  );
}
