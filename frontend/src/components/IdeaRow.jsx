import { useState } from "react";

const BADGES = {
  PENDING: ["badge-warn", "Needs approval"],
  APPROVED: ["badge-ok", "Approved"],
  IN_PROCESS: ["badge-ok", "In process"],
  REJECTED: ["badge-idle", "Rejected"],
};

const PRIORITY_LABEL = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

export default function IdeaRow({ idea, busy, onApprove, onReject }) {
  const [open, setOpen] = useState(idea.status === "PENDING");
  const [badgeClass, badgeLabel] = BADGES[idea.status] ?? BADGES.PENDING;
  const pending = idea.status === "PENDING";
  const catalogRefs = idea.catalog_refs ?? [];
  const priority = PRIORITY_LABEL[idea.priority?.toLowerCase()] || idea.priority;

  return (
    <article className={`row idea-row${open ? " is-open" : ""}`}>
      <button
        type="button"
        className="row-header"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="row-main">
          <span className="row-title">{idea.title}</span>
          <span className="row-meta">
            {idea.meeting_title && <span>{idea.meeting_title}</span>}
            {idea.meeting_title && idea.speaker && <span className="sep">·</span>}
            {idea.speaker && <span>{idea.speaker}</span>}
            {(idea.meeting_title || idea.speaker) && priority && (
              <span className="sep">·</span>
            )}
            {priority && <span>{priority} priority</span>}
            {idea.original_idea_id && (
              <>
                <span className="sep">·</span>
                <span>Seen before</span>
              </>
            )}
          </span>
        </span>

        <span className={`badge ${badgeClass}`}>{badgeLabel}</span>

        <svg className="chevron" viewBox="0 0 20 20" aria-hidden="true">
          <path d="m6 8 4 4 4-4" />
        </svg>
      </button>

      {open && (
        <div className="row-detail">
          {idea.description && (
            <section className="detail">
              <h4 className="detail-label">Summary</h4>
              <p className="detail-body">{idea.description}</p>
            </section>
          )}

          {idea.attempt_hypothesis && (
            <section className="detail">
              <h4 className="detail-label">Attempt plan</h4>
              <p className="detail-body">{idea.attempt_hypothesis}</p>
              <p className="detail-note">
                This is the catalog-grounded sketch from extraction. A full technical
                plan is produced only after you approve.
              </p>
            </section>
          )}

          {catalogRefs.length > 0 && (
            <section className="detail">
              <h4 className="detail-label">
                Catalog touchpoints{" "}
                <span className="detail-count">{catalogRefs.length}</span>
              </h4>
              <div className="chips">
                {catalogRefs.map((ref) => (
                  <span className="chip" key={ref}>{ref}</span>
                ))}
              </div>
            </section>
          )}

          {idea.quote && (
            <section className="detail">
              <h4 className="detail-label">From the meeting</h4>
              <blockquote className="idea-quote">
                “{idea.quote}”
                {(idea.speaker || idea.cue_time) && (
                  <footer>
                    {[idea.speaker, idea.cue_time].filter(Boolean).join(" · ")}
                  </footer>
                )}
              </blockquote>
            </section>
          )}

          {(idea.status === "IN_PROCESS" || idea.status === "APPROVED") && (
            <section className="detail">
              <h4 className="detail-label">Approval</h4>
              <p className="detail-body">
                Approved by {idea.approved_by || "unknown"}
                {idea.approved_at
                  ? ` · ${new Date(idea.approved_at).toLocaleString()}`
                  : ""}
              </p>
              {idea.status === "IN_PROCESS" && (
                <p className="detail-note is-ok">
                  In process — the attempt pipeline can run against this idea.
                </p>
              )}
            </section>
          )}

          {pending && (
            <div className="idea-actions">
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy}
                onClick={() => onApprove(idea.id)}
              >
                Approve
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={busy}
                onClick={() => onReject(idea.id)}
              >
                Reject
              </button>
            </div>
          )}
        </div>
      )}
    </article>
  );
}
