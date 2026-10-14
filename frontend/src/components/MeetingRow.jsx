import { useEffect, useState } from "react";
import { getMeeting } from "../api";
import { formatRelative, formatSource } from "../lib/format";
import DeleteIconButton from "./DeleteIconButton";
import Icon from "./Icon";

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
  const [details, setDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [detailsError, setDetailsError] = useState("");

  useEffect(() => {
    if (open && !details && !loadingDetails) {
      setLoadingDetails(true);
      setDetailsError("");
      getMeeting(meeting.id)
        .then((data) => setDetails(data))
        .catch((err) => setDetailsError(err.message || "Failed to load meeting details."))
        .finally(() => setLoadingDetails(false));
    }
  }, [open, meeting.id, details, loadingDetails]);

  const displayMeeting = details || meeting;
  const [badgeClass, badgeLabel] = BADGES[meeting.status] ?? BADGES.PENDING;
  const when = formatRelative(meeting.occurred_at ?? meeting.created_at);
  const minutes = displayMeeting.minutes;
  const keyPoints = minutes?.key_points ?? [];
  const actions = minutes?.action_items ?? [];
  const actionCount = actions.length || meeting.action_count || 0;
  const speakers = details?.transcript
    ? speakersIn(details.transcript)
    : (meeting.speakers ?? speakersIn(meeting.transcript));
  const canRetryIdeas =
    meeting.status === "PROCESSED" && meeting.ideas_status !== "PROCESSING";

  const statusLabel = minutesRunning
    ? "Writing minutes"
    : ideasRunning
      ? "Extracting ideas"
      : ideasFailed && meeting.status === "PROCESSED"
        ? "Ideas failed"
        : badgeLabel;
  const statusClass = pipelineRunning
    ? "badge-warn"
    : ideasFailed && meeting.status === "PROCESSED"
      ? "badge-err"
      : badgeClass;

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
          <span className="row-title-line">
            <span className="row-title">{meeting.title}</span>
            <span className={`badge badge-inline ${statusClass}`}>
              {pipelineRunning && <span className="spinner" />}
              {statusLabel}
            </span>
          </span>
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
            {actionCount > 0 && (
              <>
                <span className="sep">·</span>
                <span>
                  {actionCount} action{actionCount === 1 ? "" : "s"}
                </span>
              </>
            )}
          </span>
        </span>

        <Icon name="chevronDown" className="chevron" />
      </button>

      {open && (
        <div className="row-detail">
          {loadingDetails && !details && (
            <section className="detail status-panel">
              <div className="status-panel-head">
                <span className="spinner spinner-muted" />
                <h4 className="detail-label">Loading meeting details…</h4>
              </div>
            </section>
          )}

          {detailsError && <div className="alert alert-error">{detailsError}</div>}
          {ideasFailed && (
            <section className="detail ideas-failure">
              <div className="alert alert-error">
                <div>
                  <strong>Idea extraction failed.</strong>{" "}
                  {meeting.ideas_error || ""}
                  <p className="alert-note">Minutes were saved. Retry without re-uploading the transcript.</p>
                </div>
              </div>
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
              <div className="inline-action">
                <p className="detail-note">
                  Inbox looks empty or stale? Re-run catalog-grounded extraction.
                </p>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
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

          {displayMeeting.transcript && (
            <section className="detail">
              <button
                type="button"
                className="disclosure"
                onClick={() => setShowTranscript((v) => !v)}
              >
                {showTranscript ? "Hide" : "Show"} transcript
                <span className="detail-count">
                  {displayMeeting.transcript.split("\n").length} lines
                </span>
              </button>
              {showTranscript && (
                <pre className="transcript">{displayMeeting.transcript}</pre>
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
