export default function LoadingRows({ count = 3, label = "Loading…" }) {
  return (
    <div className="loading-block" aria-busy="true" aria-live="polite">
      <p className="loading-label">
        <span className="spinner spinner-muted" />
        {label}
      </p>
      <div className="rows">
        {Array.from({ length: count }, (_, index) => (
          <div className="skeleton" key={index} />
        ))}
      </div>
    </div>
  );
}
