/** Shared trash control used on repos, meetings, and ideas. */

export default function DeleteIconButton({
  label,
  onClick,
  disabled = false,
  busy = false,
}) {
  return (
    <button
      type="button"
      className="icon-btn btn-danger"
      title={label}
      aria-label={label}
      disabled={disabled || busy}
      onClick={onClick}
    >
      {busy ? (
        <span className="spinner spinner-muted" />
      ) : (
        <svg viewBox="0 0 16 16" aria-hidden="true">
          <path d="M5.5 1.75h5M2.75 3.75h10.5M6.25 6.25v5M9.75 6.25v5" />
          <path d="M4.25 3.75l.6 8.4a1.25 1.25 0 0 0 1.25 1.15h3.8a1.25 1.25 0 0 0 1.25-1.15l.6-8.4" />
        </svg>
      )}
    </button>
  );
}
