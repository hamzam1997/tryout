import { useState } from "react";
import { getStoredApprover, setStoredApprover } from "../lib/approver";
import { formatDateTime, formatPriority, formatRelative } from "../lib/format";
import DeleteIconButton from "./DeleteIconButton";

const BADGES = {
  PENDING: ["badge-warn", "Needs approval"],
  APPROVED: ["badge-ok", "Approved"],
  IN_PROCESS: ["badge-ok", "In process"],
  REJECTED: ["badge-idle", "Rejected"],
};

export default function IdeaRow({ idea, busy, deleting, onApprove, onReject, onDelete }) {
  const [open, setOpen] = useState(idea.status === "PENDING");
  const [approver, setApprover] = useState(() => getStoredApprover() || "local");
  const [badgeClass, badgeLabel] = BADGES[idea.status] ?? BADGES.PENDING;
  const pending = idea.status === "PENDING";
  const catalogRefs = idea.catalog_refs ?? [];
  const priority = formatPriority(idea.priority);
  const approvedWhen = formatDateTime(idea.approved_at);
  const createdWhen = formatRelative(idea.created_at);

  function handleApprove(event) {
    event.stopPropagation();
    const name = setStoredApprover(approver) || "local";
    onApprove(idea.id, name);
  }

  return (
    <article className={`row idea-row${open ? " is-open" : ""}`}>
      <button
        type="button"
        className="row-header"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="row-main">
          <span className="row-title-line">
            <span className="row-title">{idea.title}</span>
            <span className={`badge badge-inline ${badgeClass}`}>{badgeLabel}</span>
          </span>
          <span className="row-meta">
            {idea.meeting_title && <span>{idea.meeting_title}</span>}
            {idea.meeting_title && idea.speaker && <span className="sep">·</span>}
            {idea.speaker && <span>{idea.speaker}</span>}
            {(idea.meeting_title || idea.speaker) && priority && (
              <span className="sep">·</span>
            )}
            {priority && (
              <span className={`priority priority-${String(idea.priority || "").toLowerCase()}`}>
                {priority}
              </span>
            )}
            {idea.original_idea_id && (
              <>
                <span className="sep">·</span>
                <span>Seen before</span>
              </>
            )}
            {idea.approved_by && (
              <>
                <span className="sep">·</span>
                <span>by {idea.approved_by}</span>
              </>
            )}
            {createdWhen && pending && (
              <>
                <span className="sep">·</span>
                <time dateTime={idea.created_at}>{createdWhen}</time>
              </>
            )}
          </span>
        </span>

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
                Catalog-grounded sketch from extraction. A full technical plan is
                produced only after approval.
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
            <section className="detail approval-panel">
              <h4 className="detail-label">Approval</h4>
              <dl className="meta-grid">
                <div>
                  <dt>Approved by</dt>
                  <dd>{idea.approved_by || "unknown"}</dd>
                </div>
                <div>
                  <dt>Approved at</dt>
                  <dd>{approvedWhen || "—"}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>
                    {idea.status === "IN_PROCESS"
                      ? "In process — ready for an attempt"
                      : "Approved"}
                  </dd>
                </div>
              </dl>
            </section>
          )}

          {pending && (
            <div className="idea-actions-panel">
              <div className="field approver-field">
                <label htmlFor={`approver-${idea.id}`}>Approved by</label>
                <input
                  id={`approver-${idea.id}`}
                  className="input"
                  value={approver}
                  placeholder="Your name"
                  onChange={(event) => setApprover(event.target.value)}
                  onClick={(event) => event.stopPropagation()}
                />
              </div>
              <div className="idea-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={busy || deleting || !approver.trim()}
                  onClick={handleApprove}
                >
                  {busy && <span className="spinner" />}
                  {busy ? "Approving…" : "Approve"}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={busy || deleting}
                  onClick={(event) => {
                    event.stopPropagation();
                    onReject(idea.id);
                  }}
                >
                  Reject
                </button>
              </div>
            </div>
          )}

          <div className="row-footer">
            <DeleteIconButton
              label={`Delete ${idea.title}`}
              busy={deleting}
              disabled={busy}
              onClick={(event) => {
                event.stopPropagation();
                onDelete?.(idea.id);
              }}
            />
          </div>
        </div>
      )}
    </article>
  );
}
