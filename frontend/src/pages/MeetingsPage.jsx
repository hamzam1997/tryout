import MeetingRow from "../components/MeetingRow";
import Uploader from "../components/Uploader";

export default function MeetingsPage({
  meetings,
  loading,
  error,
  retryingId,
  onUploaded,
  onRefresh,
  onRetryIdeas,
}) {
  return (
    <div className="container">
      <header className="page-head">
        <div>
          <h1>Meetings</h1>
          <p className="page-sub">
            Upload a transcript for minutes, then catalog-grounded ideas. Failures
            stay on the meeting so you can retry.
          </p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={onRefresh} disabled={loading}>
          Refresh
        </button>
      </header>

      <Uploader onUploaded={onUploaded} />

      <div className="section-head">
        <h2>Recent</h2>
        {meetings.length > 0 && <span className="section-count">{meetings.length}</span>}
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading && meetings.length === 0 ? (
        <div className="rows">
          <div className="skeleton" />
          <div className="skeleton" />
        </div>
      ) : meetings.length === 0 ? (
        <div className="empty">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="3.5" y="5" width="17" height="15" rx="2" />
            <path d="M3.5 9.5h17M8.5 2.75v4M15.5 2.75v4" />
          </svg>
          <h3>No meetings yet</h3>
          <p>Upload a transcript above and it will appear here with its minutes.</p>
        </div>
      ) : (
        <div className="rows">
          {meetings.map((meeting) => (
            <MeetingRow
              key={meeting.id}
              meeting={meeting}
              retrying={retryingId === meeting.id}
              onRetryIdeas={onRetryIdeas}
            />
          ))}
        </div>
      )}
    </div>
  );
}
