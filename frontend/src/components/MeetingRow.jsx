import { useState } from "react";
import { formatRelative, formatSource } from "../lib/format";
import DeleteIconButton from "./DeleteIconButton";

const BADGES = {
  PROCESSED: ["badge-ok", "Ready"],
  PROCESSING: ["badge-warn", "Processing"],
  FAILED: ["badge-err", "Failed"],
  PENDING: ["badge-idle", "Queued"],
};

function speakersIn(transcript = "") {
  const found = new Set();
  for (const line of transcript.split("\n")) {
    const match = line.match(/^(?:\[[\d:]+\]\s*)?([^:]{1,40}):\s/);
    if (match) found.add(match[1].trim());
  }
  return [...found];
}

export default function MeetingRow({
  meeting,
  retrying,
  deleting,
  onRetryIdeas,
  onDelete,
}) {
  const minutesRunning =
    meeting.status === "PROCESSING" || meeting.status === "PENDING";
  const ideasFailed = meeting.ideas_status === "FAILED" || Boolean(meeting.ideas_error);
  const ideasRunning = meeting.ideas_status === "PROCESSING";
  const pipelineRunning = minutesRunning || ideasRunning;
  const [open, setOpen] = useState(ideasFailed);
  const [showTranscript, setShowTranscript] = useState(false);

  const [badgeClass, badgeLabel] = BADGES[meeting.status] ?? BADGES.PENDING;
  const when = formatRelative(meeting.occurred_at ?? meeting.created_at);
  const minutes = meeting.minutes;
  const keyPoints = minutes?.key_points ?? [];
  const actions = minutes?.action_items ?? [];
  const speakers = speakersIn(meeting.transcript);
  const canRetryIdeas =
    meeting.status === "PROCESSED" && meeting.ideas_status !== "PROCESSING";

  const statusLabel = minutesRunning
    ? "Writing minutes"
    : ideasRunning
      ? "Extracting ideas"
      : badgeLabel;

  return (
    <article
      className={`row${open ? " is-open" : ""}${pipelineRunning ? " is-processing" : ""}`}
    >
      {pipelineRunning && <div className="row-progress" aria-hidden="true" />}

      <button
        type="button"
        className="row-header"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="row-main">
          <span className="row-title">{meeting.title}</span>
          <span className="row-meta">
            {when && (
              <time dateTime={meeting.occurred_at ?? meeting.created_at}>{when}</time>
            )}
            {when && <span className="sep">·</span>}
            <span>{formatSource(meeting.external_source)}</span>
            {speakers.length > 0 && (
              <>
                <span className="sep">·</span>
                <span>
                  {speakers.length} speaker{speakers.length === 1 ? "" : "s"}
                </span>
              </>
            )}
            {actions.length > 0 && (
              <>
                <span className="sep">·</span>
                <span>
                  {actions.length} action{actions.length === 1 ? "" : "s"}
                </span>
              </>
            )}
            {minutesRunning && (
              <>
                <span className="sep">·</span>
                <span className="meta-live">Writing minutes…</span>
              </>
            )}
            {!minutesRunning && ideasRunning && (
              <>
                <span className="sep">·</span>
                <span className="meta-live">Extracting ideas…</span>
              </>
            )}
            {ideasFailed && (
              <>
                <span className="sep">·</span>
                <span className="meta-warn">Ideas failed</span>
              </>
            )}
          </span>
        </span>

        <span className={`badge ${pipelineRunning ? "badge-warn" : badgeClass}`}>
          {pipelineRunning && <span className="spinner" />}
          {statusLabel}
        </span>

        <svg className="chevron" viewBox="0 0 20 20" aria-hidden="true">
          <path d="m6 8 4 4 4-4" />
        </svg>
      </button>

      {open && (
        <div className="row-detail">
          {minutesRunning && (
            <section className="detail status-panel">
              <div className="status-panel-head">
                <span className="spinner spinner-muted" />
                <h4 className="detail-label">Generating minutes</h4>
              </div>
              <p className="detail-note">
                Gemini is summarizing the transcript. Catalog-grounded ideas start
                automatically when minutes land — keep this tab open or come back later.
              </p>
            </section>
          )}

          {!minutesRunning && ideasRunning && (
            <section className="detail status-panel">
              <div className="status-panel-head">
                <span className="spinner spinner-muted" />
                <h4 className="detail-label">Extracting ideas</h4>
              </div>
              <p className="detail-note">
                Matching meeting proposals to the repository catalog. New ideas will
                show up in the Ideas inbox when this finishes.
              </p>
            </section>
          )}

          {ideasFailed && (
            <section className="detail ideas-failure">
              <h4 className="detail-label">Idea extraction failed</h4>
              <div className="alert alert-error">
                {meeting.ideas_error || "Idea extraction failed."}
              </div>
              <p className="detail-note">
                Minutes were saved. Retry ideas without re-uploading the transcript.
              </p>
              {canRetryIdeas && (
                <div className="idea-actions">
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={retrying || deleting}
                    onClick={() => onRetryIdeas?.(meeting.id)}
                  >
                    {retrying && <span className="spinner" />}
                    {retrying ? "Queuing…" : "Try again"}
                  </button>
                </div>
              )}
            </section>
          )}

          {!ideasFailed && !ideasRunning && canRetryIdeas && (
            <section className="detail ideas-retry">
              <h4 className="detail-label">Ideas</h4>
              <p className="detail-note">
                Re-run catalog-grounded extraction if the inbox looks empty or stale.
              </p>
              <div className="idea-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={retrying || deleting}
                  onClick={() => onRetryIdeas?.(meeting.id)}
                >
                  {retrying && <span className="spinner" />}
                  {retrying ? "Queuing…" : "Extract ideas again"}
                </button>
              </div>
            </section>
          )}

          {!minutes && !minutesRunning && (
            <p className="detail-none">
              {meeting.status === "FAILED"
                ? "Minutes failed, but the transcript is still stored."
                : "No minutes yet."}
            </p>
          )}

          {minutes?.summary && (
            <section className="detail">
              <h4 className="detail-label">Summary</h4>
              <p className="detail-body">{minutes.summary}</p>
            </section>
          )}

          {speakers.length > 0 && (
            <section className="detail">
              <h4 className="detail-label">Speakers</h4>
              <div className="chips">
                {speakers.map((name) => (
                  <span className="chip" key={name}>{name}</span>
                ))}
              </div>
            </section>
          )}

          {keyPoints.length > 0 && (
            <section className="detail">
              <h4 className="detail-label">
                Key points <span className="detail-count">{keyPoints.length}</span>
              </h4>
              <ul className="detail-list">
                {keyPoints.map((point, i) => <li key={i}>{point}</li>)}
              </ul>
            </section>
          )}

          {actions.length > 0 && (
            <section className="detail">
              <h4 className="detail-label">
                Action items <span className="detail-count">{actions.length}</span>
              </h4>
              <ul className="detail-list is-actions">
                {actions.map((item, i) => <li key={i}>{item}</li>)}
              </ul>
            </section>
          )}

          {meeting.transcript && (
            <section className="detail">
              <button
                type="button"
                className="disclosure"
                onClick={() => setShowTranscript((v) => !v)}
              >
                {showTranscript ? "Hide" : "Show"} transcript
                <span className="detail-count">
                  {meeting.transcript.split("\n").length} lines
                </span>
              </button>
              {showTranscript && (
                <pre className="transcript">{meeting.transcript}</pre>
              )}
            </section>
          )}

          {!pipelineRunning && (
            <div className="row-footer">
              <DeleteIconButton
                label={`Delete ${meeting.title}`}
                busy={deleting}
                onClick={() => onDelete?.(meeting.id)}
              />
            </div>
          )}
        </div>
      )}
    </article>
  );
}
