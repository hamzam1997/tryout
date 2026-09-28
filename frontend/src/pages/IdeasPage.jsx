import { useMemo, useState } from "react";
import IdeaRow from "../components/IdeaRow";

const FILTERS = [
  { id: "PENDING", label: "Needs approval" },
  { id: "IN_PROCESS", label: "In process" },
  { id: "REJECTED", label: "Rejected" },
  { id: "ALL", label: "All" },
];

export default function IdeasPage({
  ideas,
  loading,
  error,
  busyId,
  onApprove,
  onReject,
  onRefresh,
}) {
  const [filter, setFilter] = useState("PENDING");

  const visible = useMemo(() => {
    if (filter === "ALL") return ideas;
    return ideas.filter((idea) => idea.status === filter);
  }, [ideas, filter]);

  const pendingCount = ideas.filter((idea) => idea.status === "PENDING").length;

  return (
    <div className="container">
      <header className="page-head">
        <div>
          <h1>Ideas</h1>
          <p className="page-sub">
            Catalog-grounded proposals from meetings. Approve one to allow an
            attempt; nothing runs until you do.
          </p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={onRefresh} disabled={loading}>
          Refresh
        </button>
      </header>

      <div className="filter-bar" role="tablist" aria-label="Idea status">
        {FILTERS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={filter === item.id}
            className={`filter-chip${filter === item.id ? " is-active" : ""}`}
            onClick={() => setFilter(item.id)}
          >
            {item.label}
            {item.id === "PENDING" && pendingCount > 0 && (
              <span className="filter-count">{pendingCount}</span>
            )}
          </button>
        ))}
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading && ideas.length === 0 ? (
        <div className="rows">
          <div className="skeleton" />
          <div className="skeleton" />
        </div>
      ) : visible.length === 0 ? (
        <div className="empty">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 3.25a5.75 5.75 0 0 0-3.25 10.5v2.5h6.5v-2.5A5.75 5.75 0 0 0 12 3.25Z" />
            <path d="M9.75 19.5h4.5" />
          </svg>
          <h3>
            {filter === "PENDING"
              ? "Nothing waiting for approval"
              : "No ideas in this view"}
          </h3>
          <p>
            Upload a meeting transcript first. The extractor only surfaces
            proposals that map onto the repository catalog.
          </p>
        </div>
      ) : (
        <div className="rows">
          {visible.map((idea) => (
            <IdeaRow
              key={idea.id}
              idea={idea}
              busy={busyId === idea.id}
              onApprove={onApprove}
              onReject={onReject}
            />
          ))}
        </div>
      )}
    </div>
  );
}
