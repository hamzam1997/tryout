import { useEffect, useState } from "react";
import { getAttempt } from "../api";
import LoadingRows from "../components/LoadingRows";
import { formatFrictionCategory } from "../lib/format";
import Icon from "../components/Icon";

// Split a unified diff into one entry per file.
function parseDiff(diff) {
  return (diff || "")
    .split(/^(?=diff --git )/m)
    .filter((chunk) => chunk.startsWith("diff --git "))
    .map((chunk) => ({
      path: chunk.slice(0, chunk.indexOf("\n")).split(" b/").pop(),
      lines: chunk.split("\n"),
    }));
}

function lineClass(line) {
  if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("diff ")) return "diff-meta";
  if (line.startsWith("@@")) return "diff-hunk";
  if (line.startsWith("+")) return "diff-add";
  if (line.startsWith("-")) return "diff-del";
  return "";
}

// A new file's content is its added lines without the leading "+".
const addedContent = (file) =>
  file.lines.filter((l) => l.startsWith("+") && !l.startsWith("+++")).map((l) => l.slice(1)).join("\n");

function Section({ title, hint, children }) {
  return (
    <section className="card report-section">
      <div className="card-head">
        <div>
          <h2>{title}</h2>
          {hint && <p className="card-hint">{hint}</p>}
        </div>
      </div>
      <div className="card-body">{children}</div>
    </section>
  );
}

export default function ReportPage({ attemptId, onBack }) {
  const [attempt, setAttempt] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getAttempt(attemptId).then(setAttempt).catch((err) => setError(err.message));
  }, [attemptId]);

  const files = parseDiff(attempt?.diff);
  // A mock is any file the friction log says stands in for a service, or one named like a mock.
  const stubPaths = new Set((attempt?.friction || []).map((log) => log.mock_implementation_path));
  const mocks = files.filter(
    (file) => stubPaths.has(file.path) || /mock/i.test(file.path.split("/").pop())
  );
  const passed = attempt?.test_exit_code === 0;

  return (
    <div className="container">
      <header className="page-head">
        <div>
          <button type="button" className="back-link" onClick={onBack}>
            <Icon name="arrowLeft" size={14} />
            Back to ideas
          </button>
          <p className="page-kicker">Step 4 · Attempt report</p>
          <h1>{attempt?.idea_title || "Attempt report"}</h1>
          {attempt?.pull_request_url && (
            <p className="page-actions">
              <a className="btn btn-secondary" href={attempt.pull_request_url} target="_blank" rel="noreferrer">
                View pull request
                <Icon name="external" size={14} />
              </a>
            </p>
          )}
        </div>
      </header>

      {error && <div className="alert alert-error">{error}</div>}
      {!attempt && !error && <LoadingRows label="Loading report…" />}

      {attempt && (
        <>
          <Section
            title="Production readiness"
            hint="What has to happen before this prototype can ship, and who owns it."
          >
            {attempt.friction.length === 0 ? (
              <p className="card-hint">No blockers were recorded for this attempt.</p>
            ) : (
              <ul className="log-list">
                {attempt.friction.map((log) => (
                  <li key={log.id} className="log-item">
                    <div className="log-top">
                      <span className="badge badge-warn">{formatFrictionCategory(log.category)}</span>
                      <strong>{log.service_name}</strong>
                      <span className="log-owner">{log.owning_team || "unknown"}</span>
                    </div>
                    <p className="log-action">{log.required_action}</p>
                    {log.mock_implementation_path && (
                      <p className="log-idea">Stubbed by {log.mock_implementation_path}</p>
                    )}
                    <ul className="log-checklist">
                      {log.readiness_checklist.map((item, i) => (
                        <li key={i}>
                          {item.task} <span className="log-owner">— {item.owner || "unassigned"}</span>
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Test results" hint="The prototype's own tests, run against the mocks.">
            {attempt.test_exit_code === null ? (
              <p className="card-hint">Tests have not run yet.</p>
            ) : (
              <>
                <span className={`badge ${passed ? "badge-ok" : "badge-err"}`}>
                  {passed ? "Passing" : `Failing (exit ${attempt.test_exit_code})`}
                </span>
                {attempt.test_stdout && <p className="detail-note">{attempt.test_stdout}</p>}
                {attempt.test_stderr && <pre className="code-block">{attempt.test_stderr}</pre>}
              </>
            )}
          </Section>

          <Section
            title="Mock adapters"
            hint="Stand-ins for services the prototype could not reach."
          >
            {mocks.length === 0 ? (
              <p className="card-hint">No mock adapters in this change.</p>
            ) : (
              mocks.map((file) => (
                <details key={file.path} className="report-file" open>
                  <summary><Icon name="file" size={14} />{file.path}</summary>
                  <pre className="code-block">{addedContent(file)}</pre>
                </details>
              ))
            )}
          </Section>

          <Section title="Code change" hint={`${files.length} ${files.length === 1 ? "file" : "files"} changed.`}>
            {files.length === 0 ? (
              <p className="card-hint">No code changes were generated.</p>
            ) : (
              files.map((file) => (
                <details key={file.path} className="report-file">
                  <summary><Icon name="file" size={14} />{file.path}</summary>
                  <pre className="code-block diff">
                    {file.lines.map((line, i) => (
                      <div key={i} className={lineClass(line)}>
                        {line || " "}
                      </div>
                    ))}
                  </pre>
                </details>
              ))
            )}
          </Section>
        </>
      )}
    </div>
  );
}
