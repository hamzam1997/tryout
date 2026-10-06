import { useEffect, useState } from "react";
import { getIdea } from "../api";
import { formatDateTime, formatPriority, formatRelative } from "../lib/format";
import DeleteIconButton from "./DeleteIconButton";

const BADGES = {
  PENDING: ["badge-warn", "Needs approval"],
  APPROVED: ["badge-ok", "Approved"],
  IN_PROCESS: ["badge-ok", "In process"],
  DONE: ["badge-ok", "Done"],
  REJECTED: ["badge-idle", "Rejected"],
};

function formatAttemptStatus(status) {
  if (status === "COMPLETE") return "done";
  if (status === "READY_FOR_REVIEW") return "ready for review";
  return String(status || "").replaceAll("_", " ").toLowerCase();
}

export default function IdeaRow({
  idea,
  repositories = [],
  busy,
  deleting,
  onApprove,
  onRetryAttempt,
  onReject,
  onDelete,
}) {
  const [open, setOpen] = useState(false);
  const [details, setDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [detailsError, setDetailsError] = useState("");
  const [repositorySelection, setRepositorySelection] = useState("");

  useEffect(() => {
    if (open) {
      setLoadingDetails(true);
      setDetailsError("");
      getIdea(idea.id)
        .then((data) => setDetails(data))
        .catch((err) => setDetailsError(err.message || "Failed to load idea details."))
        .finally(() => setLoadingDetails(false));
    }
  }, [open, idea.id, idea.latest_attempt?.status]);

  const displayIdea = details || idea;
  const [badgeClass, badgeLabel] = BADGES[idea.status] ?? BADGES.PENDING;
  const pending = idea.status === "PENDING";
  const readyRepositories = repositories.filter(
    (repository) => repository.catalog_status === "ready" && repository.catalog
  );
  const sourceRepository = readyRepositories.find(
    (repository) => repository.id === idea.repository_id
  );
  const selectedRepositoryId = repositorySelection || (
    sourceRepository
      ? String(sourceRepository.id)
      : readyRepositories.length === 1
        ? String(readyRepositories[0].id)
        : ""
  );
  const latestAttempt = displayIdea.attempts?.[0] || idea.latest_attempt;
  const catalogRefs = displayIdea.catalog_refs ?? [];
  const priority = formatPriority(idea.priority);
  const approvedWhen = formatDateTime(displayIdea.approved_at);
  const createdWhen = formatRelative(idea.created_at);

  function handleApprove(event) {
    event.stopPropagation();
    onApprove(idea.id, Number(selectedRepositoryId));
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
            {idea.latest_attempt && (
              <>
                <span className="sep">·</span>
                <span>
                  Attempt {formatAttemptStatus(idea.latest_attempt.status)}
                </span>
              </>
            )}
            {idea.latest_attempt?.pull_request_url && (
              <>
                <span className="sep">·</span>
                <a
                  className="idea-pr-link"
                  href={idea.latest_attempt.pull_request_url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(event) => event.stopPropagation()}
                >
                  View PR
                </a>
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
          {loadingDetails && !details && (
            <section className="detail status-panel">
              <div className="status-panel-head">
                <span className="spinner spinner-muted" />
                <h4 className="detail-label">Loading idea details…</h4>
              </div>
            </section>
          )}

          {detailsError && <div className="alert alert-error">{detailsError}</div>}

          {displayIdea.description && (
            <section className="detail">
              <h4 className="detail-label">Summary</h4>
              <p className="detail-body">{displayIdea.description}</p>
            </section>
          )}

          {displayIdea.attempt_hypothesis && (
            <section className="detail">
              <h4 className="detail-label">Attempt plan</h4>
              <p className="detail-body">{displayIdea.attempt_hypothesis}</p>
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

          {displayIdea.quote && (
            <section className="detail">
              <h4 className="detail-label">From the meeting</h4>
              <blockquote className="idea-quote">
                “{displayIdea.quote}”
                {(displayIdea.speaker || displayIdea.cue_time) && (
                  <footer>
                    {[displayIdea.speaker, displayIdea.cue_time].filter(Boolean).join(" · ")}
                  </footer>
                )}
              </blockquote>
            </section>
          )}

          {["IN_PROCESS", "APPROVED", "DONE"].includes(idea.status) && (
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
                      ? latestAttempt?.status
                        ? `Attempt ${latestAttempt.status.toLowerCase()}`
                        : "Attempt queued"
                    : idea.status === "DONE"
                      ? "Done"
                      : "Approved"}
                  </dd>
                </div>
              </dl>
            </section>
          )}

          {latestAttempt && (
            <section className="detail attempt-result">
              <h4 className="detail-label">
                Attempt · {formatAttemptStatus(latestAttempt.status)}
              </h4>
              {latestAttempt.error && <div className="alert alert-error">{latestAttempt.error}</div>}
              {["FAILED", "READY_FOR_REVIEW"].includes(latestAttempt.status) &&
                !latestAttempt.pull_request_url && (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={busy || deleting}
                    onClick={(event) => {
                      event.stopPropagation();
                      onRetryAttempt?.(idea.id);
                    }}
                  >
                    {busy ? <span className="spinner spinner-muted" /> : null}
                    {busy ? "Retrying…" : "Retry attempt"}
                  </button>
                )}
              {latestAttempt.pull_request_url && (
                <p className="detail-note">
                  <a href={latestAttempt.pull_request_url} target="_blank" rel="noreferrer">
                    View pull request
                  </a>
                </p>
              )}
              {latestAttempt.branch_name && !latestAttempt.pull_request_url && (
                <p className="detail-note">Generated branch: {latestAttempt.branch_name}</p>
              )}
              {latestAttempt.plan && (
                <>
                  <p className="detail-body">{latestAttempt.plan.summary}</p>
                  {latestAttempt.plan.repo_changes?.length > 0 && (
                    <ol className="attempt-steps">
                      {latestAttempt.plan.repo_changes.map((step) => (
                        <li key={`${step.order}-${step.target}`}>
                          <strong>{step.target || step.action}</strong>
                          {step.target && step.action ? ` — ${step.action}` : ""}
                          {step.rationale && <span> {step.rationale}</span>}
                        </li>
                      ))}
                    </ol>
                  )}
                  {latestAttempt.plan.external_requirements?.length > 0 && (
                    <p className="detail-note">
                      External requirements: {latestAttempt.plan.external_requirements.join(", ")}
                    </p>
                  )}
                </>
              )}

              {latestAttempt.events && latestAttempt.events.length > 0 && (
                <div className="attempt-events">
                  <h4 className="detail-subhead">Agent Harness Logs</h4>
                  <ul className="attempt-steps">
                    {latestAttempt.events.map((event, idx) => (
                      <li key={idx}>
                        <span className="timestamp">{new Date(event.timestamp).toLocaleTimeString()}</span>
                        {" - "}
                        <strong>{event.action}</strong>
                        {event.detail && <span>: {event.detail}</span>}
                        {event.status === "failed" && <span style={{color: "red"}}> (Failed)</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {latestAttempt.diff ? (
                <details className="attempt-diff">
                  <summary>View generated code change</summary>
                  <pre>{latestAttempt.diff}</pre>
                </details>
              ) : latestAttempt.status === "READY_FOR_REVIEW" ? (
                <p className="detail-note">No code changes were generated.</p>
              ) : null}
              {latestAttempt.test_stdout && (
                <p className="detail-note">{latestAttempt.test_stdout}</p>
              )}
            </section>
          )}

          {pending && (
            <div className="idea-actions-panel">
              {readyRepositories.length > 1 ? (
                <div className="field repo-attempt-field">
                  <label htmlFor={`repo-${idea.id}`}>Attempt in repository</label>
                  <select
                    id={`repo-${idea.id}`}
                    className="input"
                    value={selectedRepositoryId}
                    onChange={(event) => setRepositorySelection(event.target.value)}
                    onClick={(event) => event.stopPropagation()}
                  >
                    <option value="">Choose a repository</option>
                    {readyRepositories.map((repository) => (
                      <option key={repository.id} value={repository.id}>{repository.name}</option>
                    ))}
                  </select>
                </div>
              ) : readyRepositories.length === 1 ? (
                <p className="detail-note">
                  Attempt in <strong>{readyRepositories[0].name}</strong>
                </p>
              ) : (
                <p className="detail-note">
                  Onboard a repository and finish its architecture catalog before approving.
                </p>
              )}
              <div className="idea-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={busy || deleting || !selectedRepositoryId}
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
