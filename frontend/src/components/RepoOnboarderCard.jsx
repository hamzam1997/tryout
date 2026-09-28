import { useCallback, useEffect, useState } from "react";
import {
  deleteRepository,
  getGithubAuthStatus,
  getGithubRepos,
  listRepositories,
  logoutGithub,
  onboardRepository,
} from "../api";
import DeleteIconButton from "./DeleteIconButton";

export default function RepoOnboarderCard({
  repositories,
  onOnboarded,
  onViewCatalog,
  onDeleted,
}) {
  const [tab, setTab] = useState("github"); // "github" | "demo"
  const [authStatus, setAuthStatus] = useState({ configured: false, authenticated: false, user: null });
  const [deletingId, setDeletingId] = useState(null);
  const [ghRepos, setGhRepos] = useState([]);
  const [loadingGhRepos, setLoadingGhRepos] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedRepoFullName, setSelectedRepoFullName] = useState("");
  const [branch, setBranch] = useState("");
  const [onboarding, setOnboarding] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState(() => {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get("auth_error") ? decodeURIComponent(urlParams.get("auth_error")) : "";
  });

  // Clean URL query parameters if returned from OAuth redirect
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("auth_success") || urlParams.get("auth_error")) {
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const fetchUserRepos = useCallback(async () => {
    setLoadingGhRepos(true);
    try {
      const repos = await getGithubRepos();
      setGhRepos(repos);
      if (repos.length > 0) {
        setSelectedRepoFullName((curr) => curr || repos[0].full_name);
        setBranch((curr) => curr || repos[0].default_branch || "main");
      }
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoadingGhRepos(false);
    }
  }, []);

  // Fetch OAuth status on mount
  useEffect(() => {
    getGithubAuthStatus()
      .then((status) => {
        setAuthStatus(status);
        if (status.authenticated) {
          fetchUserRepos();
        }
      })
      .catch(() => {});
  }, [fetchUserRepos]);

  // Background polling: If any repo is currently onboarding, poll every 2.5 seconds
  const hasOnboardingRepo = repositories?.some((r) => r.catalog_status === "onboarding");

  useEffect(() => {
    if (!hasOnboardingRepo) return;

    const interval = setInterval(async () => {
      try {
        const latestRepos = await listRepositories();
        latestRepos.forEach((repo) => {
          if (onOnboarded) onOnboarded(repo);
        });
      } catch {
        // Ignore polling errors
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [hasOnboardingRepo, onOnboarded]);

  async function handleLogout() {
    try {
      await logoutGithub();
      setAuthStatus({ configured: authStatus.configured, authenticated: false, user: null });
      setGhRepos([]);
      setSelectedRepoFullName("");
    } catch (err) {
      setErrorMsg(err.message);
    }
  }

  async function handleOnboardGithub() {
    if (!selectedRepoFullName) {
      setErrorMsg("Please select a GitHub repository.");
      return;
    }
    setErrorMsg("");
    setOnboarding(true);
    setStatusMsg(`Analyzing ${selectedRepoFullName} with Gemini in the background…`);

    try {
      const res = await onboardRepository({
        sourceType: "github",
        repoFullName: selectedRepoFullName,
        branch: branch || undefined,
        forceRefresh: true,
      });
      if (onOnboarded) onOnboarded(res.repository);
      setStatusMsg("Onboarding is running in the background. You can refresh safely.");
      setTimeout(() => {
        setOnboarding(false);
        setStatusMsg("");
      }, 3000);
    } catch (err) {
      setErrorMsg(err.message);
      setOnboarding(false);
      setStatusMsg("");
    }
  }

  async function handleOnboardDemo() {
    setErrorMsg("");
    setOnboarding(true);
    setStatusMsg("Analyzing Acme Store sandbox in the background with Gemini…");

    try {
      const res = await onboardRepository({
        sourceType: "demo",
        forceRefresh: true,
      });
      if (onOnboarded) onOnboarded(res.repository);
      setStatusMsg("Onboarding is running in the background. You can refresh safely.");
      setTimeout(() => {
        setOnboarding(false);
        setStatusMsg("");
      }, 3000);
    } catch (err) {
      setErrorMsg(err.message);
      setOnboarding(false);
      setStatusMsg("");
    }
  }

  async function handleDeleteRepo(repoId, repoName) {
    if (!window.confirm(`Are you sure you want to remove '${repoName}'?`)) {
      return;
    }
    setDeletingId(repoId);
    setErrorMsg("");
    try {
      await deleteRepository(repoId);
      if (onDeleted) {
        onDeleted(repoId);
      }
    } catch (err) {
      setErrorMsg(err.message || "Failed to remove repository");
    } finally {
      setDeletingId(null);
    }
  }

  const filteredRepos = ghRepos.filter(
    (r) =>
      r.full_name.toLowerCase().includes(search.toLowerCase()) ||
      (r.description && r.description.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="card onboarding-card">
      <div className="card-head">
        <div>
          <p className="card-eyebrow">Architecture intake</p>
          <h2>Onboard a repository</h2>
          <p className="card-hint">
            Connect once. Gemini maps modules, routes, and owners into a shared
            catalog — the filter every later idea must pass.
          </p>
        </div>
      </div>

      <div className="card-body">
        {/* Source Mode Tabs */}
        <div className="onboarding-tabs">
          <button
            type="button"
            className={`tab-btn ${tab === "github" ? "is-active" : ""}`}
            onClick={() => { setTab("github"); setErrorMsg(""); }}
          >
            <svg className="tab-icon" viewBox="0 0 16 16" aria-hidden="true">
              <path fillRule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
            </svg>
            GitHub Integration
          </button>
          <button
            type="button"
            className={`tab-btn ${tab === "demo" ? "is-active" : ""}`}
            onClick={() => { setTab("demo"); setErrorMsg(""); }}
          >
            One-Click Demo Repo
          </button>
        </div>

        {errorMsg && <div className="alert alert-error">{errorMsg}</div>}

        {/* Tab 1: GitHub Connection */}
        {tab === "github" && (
          <div className="tab-pane">
            {!authStatus.authenticated ? (
              <div className="github-connect-box">
                <div className="connect-prompt">
                  <h3>Connect with GitHub</h3>
                  <p>
                    Authenticate securely via OAuth to select and onboard any of your public or private repositories.
                  </p>
                </div>
                {authStatus.configured ? (
                  <a href="/api/auth/github/login" className="btn btn-primary btn-github">
                    <svg className="btn-icon" viewBox="0 0 16 16" aria-hidden="true">
                      <path fillRule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
                    </svg>
                    Connect with GitHub
                  </a>
                ) : (
                  <div className="notice-banner">
                    <p>
                      <strong>GitHub OAuth App not yet configured.</strong> Configure <code>GITHUB_CLIENT_ID</code> and <code>GITHUB_CLIENT_SECRET</code> in the environment, or use the <strong>One-Click Demo Repo</strong>.
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="github-authenticated-box">
                <div className="user-profile-bar">
                  <div className="user-info">
                    {authStatus.user?.avatar_url && (
                      <img src={authStatus.user.avatar_url} alt="" className="avatar" />
                    )}
                    <span>Connected as <strong>@{authStatus.user?.login}</strong></span>
                  </div>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={handleLogout}>
                    Disconnect
                  </button>
                </div>

                {loadingGhRepos ? (
                  <div className="loading-repos">Loading repositories from GitHub…</div>
                ) : (
                  <div className="repo-selection-form">
                    <div className="form-group">
                      <label htmlFor="repo-search">Select Repository</label>
                      <input
                        id="repo-search"
                        type="text"
                        placeholder="Search your repositories…"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="input"
                      />
                    </div>

                    <div className="repo-picker-list">
                      {filteredRepos.length === 0 ? (
                        <p className="empty-subtext">No repositories match your search.</p>
                      ) : (
                        filteredRepos.slice(0, 15).map((r) => (
                          <label
                            key={r.id}
                            className={`repo-radio-item ${selectedRepoFullName === r.full_name ? "is-selected" : ""}`}
                          >
                            <input
                              type="radio"
                              name="selected_repo"
                              value={r.full_name}
                              checked={selectedRepoFullName === r.full_name}
                              onChange={() => {
                                setSelectedRepoFullName(r.full_name);
                                setBranch(r.default_branch || "main");
                              }}
                            />
                            <div className="repo-item-content">
                              <div className="repo-item-title">
                                <span className="repo-name">{r.full_name}</span>
                                {r.private ? (
                                  <span className="badge badge-private">Private</span>
                                ) : (
                                  <span className="badge badge-public">Public</span>
                                )}
                              </div>
                              {r.description && <p className="repo-item-desc">{r.description}</p>}
                            </div>
                          </label>
                        ))
                      )}
                    </div>

                    <div className="form-row-actions">
                      <div className="form-group-inline">
                        <label htmlFor="branch-input">Branch</label>
                        <input
                          id="branch-input"
                          type="text"
                          value={branch}
                          onChange={(e) => setBranch(e.target.value)}
                          placeholder="main"
                          className="input input-sm"
                        />
                      </div>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={handleOnboardGithub}
                        disabled={onboarding || !selectedRepoFullName}
                      >
                        {onboarding ? "Starting…" : "Onboard Repository"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Demo Sandbox */}
        {tab === "demo" && (
          <div className="tab-pane">
            <div className="demo-box">
              <div className="demo-info">
                <h3>Acme Store Sandbox Service</h3>
                <p>
                  A realistic microservice repository featuring inventory management, orders, Stripe payments adapter, and missing notification permissions designed to exercise prototype attempts and friction detection.
                </p>
                <div className="specs-preview">
                  <span>Stack: <strong>Python / Flask</strong></span>
                  <span>Path: <code>demo_repo/acme_store</code></span>
                  <span>Contains: Models, Routes, CODEOWNERS</span>
                </div>
              </div>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleOnboardDemo}
                disabled={onboarding}
              >
                {onboarding ? (
                  <>
                    <span className="spinner" />
                    Starting…
                  </>
                ) : (
                  "Connect Acme Store demo"
                )}
              </button>
            </div>
          </div>
        )}

        {/* Progress or status banner */}
        {statusMsg && (
          <div className="onboarding-status-pill">
            <span className="spinner" />
            <span>{statusMsg}</span>
          </div>
        )}

        {/* Already Onboarded Repositories Section */}
        {repositories && repositories.length > 0 && (
          <div className="onboarded-repos-section">
            <h3>Connected Codebases</h3>
            <div className="repos-grid">
              {repositories.map((repo) => {
                const isOnboarding = repo.catalog_status === "onboarding";
                const isFailed = repo.catalog_status === "failed";

                return (
                  <div key={repo.id} className="repo-summary-card">
                    <div className="repo-card-head">
                      <div className="repo-card-title">
                        <strong>{repo.name}</strong>
                        <span className={`badge badge-${repo.source_type}`}>{repo.source_type}</span>
                      </div>

                      <div className="repo-card-actions">
                        {isOnboarding ? (
                          <span className="badge badge-warn status-pulse">
                            <span className="spinner spinner-xs" /> Analyzing…
                          </span>
                        ) : isFailed ? (
                          <span className="badge badge-err">Failed</span>
                        ) : null}
                        {!isOnboarding && (
                          <DeleteIconButton
                            label={`Remove ${repo.name}`}
                            busy={deletingId === repo.id}
                            onClick={() => handleDeleteRepo(repo.id, repo.name)}
                          />
                        )}
                      </div>
                    </div>

                    <p className="repo-source-sub"><code>{repo.source}</code></p>

                    {isOnboarding && (
                      <p className="repo-analyzing-note">
                        Gemini 2.5 Flash is analyzing architecture modules, data models, routes, and team owners in the background…
                      </p>
                    )}

                    {isFailed && (
                      <p className="repo-error-note">
                        {repo.catalog_error || "Analysis failed."}
                      </p>
                    )}

                    {!isOnboarding && !isFailed && repo.catalog && (
                      <div className="repo-card-stats">
                        <span>{repo.catalog.language}</span>
                        {repo.catalog.framework && <span>• {repo.catalog.framework}</span>}
                        {repo.catalog.modules?.length > 0 && (
                          <span>• {repo.catalog.modules.length} modules</span>
                        )}
                        {repo.catalog.api_routes?.length > 0 && (
                          <span>• {repo.catalog.api_routes.length} routes</span>
                        )}
                      </div>
                    )}

                    {!isOnboarding && !isFailed && (
                      <div className="repo-card-foot">
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm repo-catalog-link"
                          onClick={() => onViewCatalog(repo)}
                        >
                          View Catalog →
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
