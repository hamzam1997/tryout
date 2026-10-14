import { useEffect, useRef, useState } from "react";
import Icon from "./Icon";

// Streams /attempts/<id>/stream into a terminal view; hands off to the report when done.
export default function LiveAttemptModal({ attemptId, onClose, onDone }) {
  const dialogRef = useRef(null);
  const endRef = useRef(null);
  const [status, setStatus] = useState("QUEUED");
  const [steps, setSteps] = useState([]);

  useEffect(() => {
    dialogRef.current?.showModal();
    const source = new EventSource(`/api/attempts/${attemptId}/stream`);
    source.addEventListener("status", (e) => setStatus(JSON.parse(e.data).status));
    source.addEventListener("step", (e) => setSteps((current) => [...current, JSON.parse(e.data)]));
    source.addEventListener("done", () => {
      source.close();
      onDone(attemptId);
    });
    return () => source.close();
  }, [attemptId, onDone]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [steps]);

  return (
    <dialog ref={dialogRef} className="live-modal" onClose={onClose} aria-label="Live attempt">
      <header className="live-head">
        <div>
          <p className="card-eyebrow">Attempt #{attemptId}</p>
          <h2>Agent at work</h2>
        </div>
        <span className="live-head-actions">
          <span className="badge badge-warn">
            <span className="spinner" />
            {status.charAt(0) + status.slice(1).toLowerCase()}
          </span>
          <button type="button" className="icon-btn" aria-label="Close" onClick={() => dialogRef.current?.close()}>
            <Icon name="close" />
          </button>
        </span>
      </header>
      <pre className="terminal" aria-live="polite">
        {steps.length === 0 && <div className="terminal-muted">Waiting for the agent to start…</div>}
        {steps.map((step, i) => (
          <div key={i} className={step.status === "failed" ? "terminal-err" : ""}>
            <span className="terminal-muted">{new Date(step.timestamp).toLocaleTimeString()}</span>{" "}
            <strong>{step.action}</strong> {step.detail}
          </div>
        ))}
        <div ref={endRef} />
      </pre>
      <footer className="live-foot">
        <span className="card-hint">Opens the report automatically when the attempt finishes.</span>
        <button type="button" className="btn btn-secondary" onClick={() => dialogRef.current?.close()}>
          Run in background
        </button>
      </footer>
    </dialog>
  );
}
