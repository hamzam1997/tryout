import IdeaRow from "../components/IdeaRow";
import LoadingRows from "../components/LoadingRows";

const FILTERS = [
  { id: "PENDING", label: "Needs approval" },
  { id: "IN_PROCESS", label: "In process" },
  { id: "REJECTED", label: "Rejected" },
  { id: "ALL", label: "All" },
];

export default function IdeasPage({
  ideas,
  repositories = [],
  counts,
  filter = "PENDING",
  onFilterChange,
  loading,
  error,
  busyId,
  deletingId,
  onApprove,
  onRetryAttempt,
  onReject,
  onDelete,
}) {

  return (
    <div className="container">
      <header className="page-head">
        <div>
          <p className="page-kicker">Step 3 · Human gate</p>
          <h1>Ideas</h1>
          <p className="page-sub">
            Catalog-grounded proposals from meetings. Approve an idea to generate a
            repo-specific plan and code change for review.
          </p>
        </div>
      </header>

      <div className="filter-bar" role="tablist" aria-label="Idea status">
        {FILTERS.map((item) => {
          const count =
            counts && counts[item.id] !== undefined
              ? counts[item.id]
              : item.id === "ALL"
                ? counts?.ALL ?? ideas.length
                : null;
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={filter === item.id}
              className={`filter-chip${filter === item.id ? " is-active" : ""}`}
              onClick={() => onFilterChange?.(item.id)}
            >
              {item.label}
              {count > 0 && <span className="filter-count">{count}</span>}
            </button>
          );
        })}
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading && ideas.length === 0 ? (
        <LoadingRows label="Loading ideas…" />
      ) : ideas.length === 0 ? (
        <div className="empty">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 3.25a5.75 5.75 0 0 0-3.25 10.5v2.5h6.5v-2.5A5.75 5.75 0 0 0 12 3.25Z" />
            <path d="M9.75 19.5h4.5" />
          </svg>
          <h3>
            {filter === "PENDING"
              ? "Inbox clear"
              : filter === "IN_PROCESS"
                ? "No ideas in process"
                : "No ideas in this view"}
          </h3>
          <p>
            {filter === "PENDING"
              ? "When a meeting finishes extraction, attemptable ideas land here for your approval."
              : "Upload a meeting with an onboarded repository catalog to generate ideas."}
          </p>
        </div>
      ) : (
        <div className="rows">
          {ideas.map((idea) => (
            <IdeaRow
              key={idea.id}
              idea={idea}
              repositories={repositories}
              busy={busyId === idea.id}
              deleting={deletingId === idea.id}
              onApprove={onApprove}
              onRetryAttempt={onRetryAttempt}
              onReject={onReject}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}
