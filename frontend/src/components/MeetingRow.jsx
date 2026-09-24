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

export default function MeetingRow({ meeting }) {
  const [badgeClass, badgeLabel] = BADGES[meeting.status] ?? BADGES.PENDING;
  const when = formatDate(meeting.occurred_at ?? meeting.created_at);
  const actions = meeting.minutes?.action_items ?? [];

  return (
    <article className="row">
      <div>
        <h3 className="row-title">{meeting.title}</h3>

        <div className="row-meta">
          {when && <span>{when}</span>}
          {when && <span className="sep">·</span>}
          <span>{meeting.external_source}</span>
          {actions.length > 0 && (
            <>
              <span className="sep">·</span>
              <span>{actions.length} action {actions.length === 1 ? "item" : "items"}</span>
            </>
          )}
        </div>

        {meeting.minutes?.summary && (
          <p className="row-summary">{meeting.minutes.summary}</p>
        )}

        {actions.length > 0 && (
          <div className="chips">
            {actions.slice(0, 3).map((item, index) => (
              <span className="chip" key={index}>
                {item.length > 64 ? `${item.slice(0, 64)}…` : item}
              </span>
            ))}
            {actions.length > 3 && <span className="chip">+{actions.length - 3} more</span>}
          </div>
        )}
      </div>

      <span className={`badge ${badgeClass}`}>{badgeLabel}</span>
    </article>
  );
}
