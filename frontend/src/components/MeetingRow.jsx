import { useState } from "react";

const BADGES = {
  PROCESSED: ["badge-ok", "Processed"],
  PROCESSING: ["badge-warn", "Processing"],
  FAILED: ["badge-err", "Failed"],
  PENDING: ["badge-idle", "Pending"],
};

function formatDate(value) {
  if (!value) return null;
  return new Date(value).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function speakersIn(transcript = "") {
  const found = new Set();
  for (const line of transcript.split("\n")) {
    const match = line.match(/^(?:\[[\d:]+\]\s*)?([^:]{1,40}):\s/);
    if (match) found.add(match[1].trim());
  }
  return [...found];
}

export default function MeetingRow({ meeting, retrying, onRetryIdeas }) {
  const ideasFailed = meeting.ideas_status === "FAILED" || Boolean(meeting.ideas_error);
  const ideasRunning = meeting.ideas_status === "PROCESSING";
  const [open, setOpen] = useState(ideasFailed);
  const [showTranscript, setShowTranscript] = useState(false);

  const [badgeClass, badgeLabel] = BADGES[meeting.status] ?? BADGES.PENDING;
  const when = formatDate(meeting.occurred_at ?? meeting.created_at);
  const minutes = meeting.minutes;
  const keyPoints = minutes?.key_points ?? [];
  const actions = minutes?.action_items ?? [];
  const speakers = speakersIn(meeting.transcript);
  const canRetryIdeas =
    meeting.status === "PROCESSED" && meeting.ideas_status !== "PROCESSING";

  return (
    <article className={`row${open ? " is-open" : ""}`}>
      <button
        type="button"
        className="row-header"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="row-main">
          <span className="row-title">{meeting.title}</span>
          <span className="row-meta">
            {when && <span>{when}</span>}
            {when && <span className="sep">·</span>}
            <span>{meeting.external_source}</span>
            {speakers.length > 0 && (
              <>
                <span className="sep">·</span>
                <span>{speakers.length} speakers</span>
              </>
            )}
            {actions.length > 0 && (
              <>
                <span className="sep">·</span>
                <span>{actions.length} action {actions.length === 1 ? "item" : "items"}</span>
              </>
            )}
            {ideasRunning && (
              <>
                <span className="sep">·</span>
                <span className="meta-warn">Extracting ideas…</span>
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

        <span className={`badge ${badgeClass}`}>{badgeLabel}</span>

        <svg className="chevron" viewBox="0 0 20 20" aria-hidden="true">
          <path d="m6 8 4 4 4-4" />
        </svg>
      </button>

      {open && (
        <div className="row-detail">
          {ideasRunning && (
            <section className="detail">
              <h4 className="detail-label">Ideas</h4>
              <p className="detail-note">
                Idea extraction is running in the background. This page refreshes
                automatically when it finishes.
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
                Minutes were saved. Ideas can be retried without re-uploading the transcript.
              </p>
              {canRetryIdeas && (
                <div className="idea-actions">
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={retrying}
                    onClick={() => onRetryIdeas?.(meeting.id)}
                  >
                    {retrying && <span className="spinner" />}
                    {retrying ? "Queuing" : "Try again"}
                  </button>
                </div>
              )}
            </section>
          )}

          {!ideasFailed && !ideasRunning && canRetryIdeas && (
            <section className="detail ideas-retry">
              <h4 className="detail-label">Ideas</h4>
              <p className="detail-note">
                Re-queue catalog-grounded idea extraction for this meeting if the inbox looks empty.
              </p>
              <div className="idea-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={retrying}
                  onClick={() => onRetryIdeas?.(meeting.id)}
                >
                  {retrying && <span className="spinner" />}
                  {retrying ? "Queuing" : "Extract ideas again"}
                </button>
              </div>
            </section>
          )}

          {!minutes && (
            <p className="detail-none">
              {meeting.status === "FAILED"
                ? "Extraction failed, so there are no minutes. The transcript is still stored."
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
        </div>
      )}
    </article>
  );
}
