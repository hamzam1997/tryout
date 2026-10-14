import { useCallback, useEffect, useState } from "react";
import {
  deleteRepository,
  getGithubAuthStatus,
  getGithubRepos,
  listRepositories,
  logoutGithub,
  onboardRepository,
} from "../api";
import { loginWithGitHub, logoutUser } from "../lib/firebase";
import DeleteIconButton from "./DeleteIconButton";
import Icon from "./Icon";

const GITHUB_PREFIX = "https://github.com/";
const shortSource = (source = "") => source.replace(GITHUB_PREFIX, "");

export default function RepoOnboarderCard({
  repositories,
  onOnboarded,
  onViewCatalog,
  loadingCatalogId,
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
      await logoutUser();
      await logoutGithub().catch(() => {});
      setAuthStatus({ configured: authStatus.configured, authenticated: false, user: null });
      setGhRepos([]);
      setSelectedRepoFullName("");
    } catch (err) {
      setErrorMsg(err.message);
    }
  }

  async function handleConnectWithGitHub() {
    setErrorMsg("");
    try {
      const { user } = await loginWithGitHub();
      const loginName = user.reloadUserInfo?.screenName || user.displayName || user.email;
      setAuthStatus({
        configured: true,
        authenticated: true,
        user: { login: loginName, avatar_url: user.photoURL },
      });
      await fetchUserRepos();
    } catch (err) {
      console.warn("Firebase GitHub popup failed or cancelled, trying server redirect:", err);
      if (authStatus.configured) {
        window.location.href = "/api/auth/github/login";
      } else {
        setErrorMsg(err.message || "Failed to sign in with GitHub.");
      }
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

  async function handleRetry(repo) {
    setErrorMsg("");
    try {
      const res = await onboardRepository(
        repo.source_type === "demo"
          ? { sourceType: "demo", forceRefresh: true }
          : { sourceType: "github", repoFullName: shortSource(repo.source), forceRefresh: true }
      );
      if (onOnboarded) onOnboarded(res.repository);
    } catch (err) {
      setErrorMsg(err.message);
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
          <h2>Onboard a repository</h2>
          <p className="card-hint">
            Pick a source. Analysis runs in the background, so you can leave this page.
          </p>
        </div>
      </div>

      <div className="card-body">
        {/* Source Mode Tabs */}
        <div className="onboarding-tabs" role="tablist" aria-label="Repository source">
          <button
            type="button"
            className={`tab-btn ${tab === "github" ? "is-active" : ""}`}
            role="tab"
            aria-selected={tab === "github"}
            onClick={() => { setTab("github"); setErrorMsg(""); }}
          >
            <svg className="tab-icon" viewBox="0 0 16 16" aria-hidden="true">
              <path fillRule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
            </svg>
            GitHub
          </button>
          <button
            type="button"
            className={`tab-btn ${tab === "demo" ? "is-active" : ""}`}
            role="tab"
            aria-selected={tab === "demo"}
            onClick={() => { setTab("demo"); setErrorMsg(""); }}
          >
            Demo repository
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
                    Sign in with GitHub to pick any public or private repository you can read.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleConnectWithGitHub}
                  className="btn btn-dark btn-github"
                >
                  <svg className="btn-icon" viewBox="0 0 16 16" aria-hidden="true">
                    <path fillRule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
                  </svg>
                  Connect with GitHub
                </button>
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
                    <div className="repo-search-row">
                      <label htmlFor="repo-search">Select repository</label>
                      <input
                        id="repo-search"
                        type="search"
                        placeholder="Search your repositories…"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="input repo-search-input"
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
                        {onboarding ? "Starting…" : "Onboard repository"}
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
                <h3>Acme Store sandbox</h3>
                <p>
                  A small Flask service with orders, refunds and a Stripe adapter. It is missing a notifications permission on purpose, so attempts hit a real blocker.
                </p>
                <div className="specs-preview">
                  <span><span className="spec-label">Stack</span>Python · Flask</span>
                  <span><span className="spec-label">Repository</span><a href="https://github.com/hamzam1997/acme-store" target="_blank" rel="noreferrer">hamzam1997/acme-store</a></span>
                  <span><span className="spec-label">Includes</span>Models, routes, CODEOWNERS</span>
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
                  "Connect demo repository"
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
            <div className="subsection-head">
              <h3>Connected repositories</h3>
              <span className="section-count">{repositories.length}</span>
            </div>
            <div className="repos-grid">
              {repositories.map((repo) => {
                const isOnboarding = repo.catalog_status === "onboarding";
                const isFailed = repo.catalog_status === "failed";

                return (
                  <div key={repo.id} className="repo-summary-card">
                    <div className="repo-card-head">
                      <div className="repo-card-title">
                        <strong className="repo-card-name">{repo.name}</strong>
                        <span className="repo-source-sub">
                          {repo.source_type === "demo" ? "Demo" : repo.source_type === "github" ? "GitHub" : "Local"}
                          {" · "}
                          <code>{shortSource(repo.source)}</code>
                        </span>
                      </div>

                      <div className="repo-card-actions">
                        {isOnboarding ? (
                          <span className="badge badge-warn">
                            <span className="spinner" /> Analyzing
                          </span>
                        ) : isFailed ? (
                          <span className="badge badge-err">Failed</span>
                        ) : (
                          <span className="badge badge-ok">Ready</span>
                        )}
                        {!isOnboarding && (
                          <DeleteIconButton
                            label={`Remove ${repo.name}`}
                            busy={deletingId === repo.id}
                            onClick={() => handleDeleteRepo(repo.id, repo.name)}
                          />
                        )}
                      </div>
                    </div>


                    {isOnboarding && (
                      <p className="repo-analyzing-note">
                        Mapping modules, data models, routes and owners…
                      </p>
                    )}

                    {isFailed && (
                      <p className="repo-error-note">
                        {repo.catalog_error || "Analysis failed."}
                      </p>
                    )}

                    {!isOnboarding && !isFailed && repo.catalog && (
                      <p className="repo-card-stats">
                        {[
                          repo.catalog.language,
                          repo.catalog.framework,
                          repo.catalog.modules?.length > 0 && `${repo.catalog.modules.length} modules`,
                          repo.catalog.api_routes?.length > 0 && `${repo.catalog.api_routes.length} routes`,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    )}

                    {isFailed && (
                      <div className="repo-card-foot">
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleRetry(repo)}
                          disabled={onboarding}
                        >
                          <Icon name="refresh" size={14} />
                          Retry analysis
                        </button>
                      </div>
                    )}

                    {!isOnboarding && !isFailed && (
                      <div className="repo-card-foot">
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm repo-catalog-link"
                          onClick={() => onViewCatalog(repo)}
                          disabled={loadingCatalogId === repo.id}
                        >
                          {loadingCatalogId === repo.id ? (
                            <>
                              <span className="spinner spinner-xs" /> Loading catalog…
                            </>
                          ) : (
                            <>
                              View catalog
                              <Icon name="arrowRight" size={14} />
                            </>
                          )}
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
