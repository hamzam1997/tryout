export default function IdeasPage() {
  return (
    <div className="container">
      <header className="page-head">
        <div>
          <h1>Ideas</h1>
          <p className="page-sub">
            Proposals pulled out of meetings, waiting for someone to approve them.
          </p>
        </div>
      </header>

      <div className="empty">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3.25a5.75 5.75 0 0 0-3.25 10.5v2.5h6.5v-2.5A5.75 5.75 0 0 0 12 3.25Z" />
          <path d="M9.75 19.5h4.5" />
        </svg>
        <h3>No ideas yet</h3>
        <p>
          The idea extractor reads stored transcripts and separates real proposals
          from status updates. Approved ones get attempted against a repository.
        </p>
      </div>
    </div>
  );
}
