import { useEffect, useState } from "react";
import { getBottlenecks } from "../api";
import LoadingRows from "../components/LoadingRows";
import { formatFrictionCategory as label } from "../lib/format";

function Stat({ value, name, hint }) {
  return (
    <div className="card stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-name">{name}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

function BarChart({ title, hint, rows, format = (name) => name, activeName, onPick }) {
  const max = Math.max(1, ...rows.map((row) => row.count));
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>{title}</h2>
          <p className="card-hint">{hint}</p>
        </div>
      </div>
      <div className="card-body">
        {rows.length === 0 ? (
          <p className="card-hint">No data yet.</p>
        ) : (
          <ul className="bars">
            {rows.map((row) => (
              <li key={row.name}>
                <button
                  type="button"
                  className={`bar-row${activeName === row.name ? " is-active" : ""}`}
                  onClick={() => onPick?.(activeName === row.name ? null : row.name)}
                  aria-pressed={activeName === row.name}
                >
                  <span className="bar-label">{format(row.name)}</span>
                  <span className="bar-track">
                    <span className="bar-fill" style={{ width: `${(row.count / max) * 100}%` }} />
                  </span>
                  <span className="bar-count">{row.count}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

export default function BottlenecksPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [category, setCategory] = useState(null);
  const [team, setTeam] = useState(null);
  const [service, setService] = useState(null);

  useEffect(() => {
    getBottlenecks().then(setData).catch((err) => setError(err.message));
  }, []);

  const logs = (data?.logs || []).filter(
    (log) =>
      (!category || log.category === category) &&
      (!team || log.owning_team === team) &&
      (!service || log.service_name === service)
  );
  const filtering = category || team || service;

  return (
    <div className="container">
      <header className="page-head">
        <div>
          <p className="page-kicker">Step 5 · Organization view</p>
          <h1>Bottleneck map</h1>
          <p className="page-sub">
            Every blocker the agent hit across all attempts. Click any bar to filter the log below.
          </p>
        </div>
      </header>

      {error && <div className="alert alert-error">{error}</div>}
      {!data && !error && <LoadingRows label="Loading bottlenecks…" />}

      {data && (
        <>
          <div className="stat-grid" data-tour="bottleneck-stats">
            <Stat value={data.total} name="Blockers found" hint="Before any work was committed" />
            <Stat value={data.attempts} name="Attempts analysed" />
            <Stat
              value={`~${data.weeks_saved}`}
              name="Eng. weeks saved (est.)"
              hint="Assumes 1–2 weeks lost per blocker found late"
            />
          </div>

          <div className="chart-grid">
            <BarChart
              title="Friction categories"
              hint="What kind of work is blocking ideas."
              rows={data.by_category}
              format={label}
              activeName={category}
              onPick={setCategory}
            />
            <BarChart
              title="External dependencies"
              hint="Services that block ideas most often."
              rows={data.by_service}
              activeName={service}
              onPick={setService}
            />
            <BarChart
              title="Team leaderboard"
              hint="Teams that other work waits on."
              rows={data.by_team}
              activeName={team}
              onPick={setTeam}
            />
          </div>

          <section className="card log-card">
            <div className="card-head">
              <div>
                <h2>Friction log</h2>
                <p className="card-hint">
                  {logs.length} of {data.total} blockers
                  {filtering && (
                    <>
                      {" · "}
                      <button
                        type="button"
                        className="link-btn"
                        onClick={() => {
                          setCategory(null);
                          setTeam(null);
                          setService(null);
                        }}
                      >
                        Clear filters
                      </button>
                    </>
                  )}
                </p>
              </div>
            </div>
            <div className="card-body">
              {logs.length === 0 ? (
                <p className="card-hint">No blockers match these filters.</p>
              ) : (
                <ul className="log-list">
                  {logs.map((log) => (
                    <li key={log.id} className="log-item">
                      <div className="log-top">
                        <span className="badge badge-warn">{label(log.category)}</span>
                        <strong>{log.service_name}</strong>
                        <span className="log-owner">{log.owning_team}</span>
                      </div>
                      <p className="log-action">{log.required_action}</p>
                      <p className="log-idea">From idea: {log.idea_title || "—"}</p>
                      {log.readiness_checklist.length > 0 && (
                        <ul className="log-checklist">
                          {log.readiness_checklist.map((item, i) => (
                            <li key={i}>
                              {item.task} <span className="log-owner">— {item.owner || "unassigned"}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
