import LoadingRows from "../components/LoadingRows";
import MeetingRow from "../components/MeetingRow";
import Uploader from "../components/Uploader";

export default function MeetingsPage({
  meetings,
  loading,
  error,
  retryingId,
  deletingId,
  onUploaded,
  onRetryIdeas,
  onDelete,
}) {
  const running = meetings.filter(
    (meeting) =>
      meeting.status === "PROCESSING" ||
      meeting.status === "PENDING" ||
      meeting.ideas_status === "PROCESSING"
  ).length;

  return (
    <div className="container">
      <header className="page-head">
        <div>
          <p className="page-kicker">Step 2 · Capture signal</p>
          <h1>Meetings</h1>
          <p className="page-sub">
            Drop a transcript — minutes and catalog-grounded ideas run in the
            background so you can keep uploading.
          </p>
        </div>
      </header>

      <Uploader onUploaded={onUploaded} />

      <div className="section-head">
        <h2>Recent</h2>
        {meetings.length > 0 && <span className="section-count">{meetings.length}</span>}
        {running > 0 && (
          <span className="section-live">
            <span className="spinner spinner-muted" />
            {running} processing
          </span>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading && meetings.length === 0 ? (
        <LoadingRows label="Loading meetings…" />
      ) : meetings.length === 0 ? (
        <div className="empty">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="3.5" y="5" width="17" height="15" rx="2" />
            <path d="M3.5 9.5h17M8.5 2.75v4M15.5 2.75v4" />
          </svg>
          <h3>No meetings yet</h3>
          <p>
            Upload a transcript above. It appears here immediately while minutes
            and ideas finish in the background.
          </p>
        </div>
      ) : (
        <div className="rows" data-tour="meeting-list">
          {meetings.map((meeting) => (
            <MeetingRow
              key={meeting.id}
              meeting={meeting}
              retrying={retryingId === meeting.id}
              deleting={deletingId === meeting.id}
              onRetryIdeas={onRetryIdeas}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}
