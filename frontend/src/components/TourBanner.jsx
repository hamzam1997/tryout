// The five-step demo journey, shown above every page.
const STEPS = [
  { view: "repositories", label: "Onboard repo" },
  { view: "meetings", label: "Ingest meeting" },
  { view: "ideas", label: "Approve idea" },
  { view: "report", label: "Run tryout" },
  { view: "bottlenecks", label: "Bottleneck map" },
];

export default function TourBanner({ view, done, onNavigate }) {
  return (
    <nav className="tour" aria-label="Demo journey">
      <ol>
        {STEPS.map((step, i) => {
          const current = step.view === view;
          const state = current ? "is-current" : done[i] ? "is-done" : "";
          return (
            <li key={step.view}>
              <button
                type="button"
                className={`tour-step ${state}`}
                aria-current={current ? "step" : undefined}
                // The report needs an attempt; its step leads to the ideas where attempts live.
                onClick={() => onNavigate(step.view === "report" ? "ideas" : step.view)}
              >
                <span className="tour-num">{done[i] && !current ? "✓" : i + 1}</span>
                {step.label}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
