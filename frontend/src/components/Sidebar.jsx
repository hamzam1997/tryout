import { useEffect, useState } from "react";
import { loginWithGoogle, logoutUser, onAuthChanged } from "../lib/firebase";
import WorkspaceSwitcher from "./WorkspaceSwitcher";

const ICONS = {
  repositories: (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5v-9zm10.5-1h-8a1 1 0 0 0-1 1v6.7c.28-.13.59-.2.928-.2h8.072V1.5z" />
    </svg>
  ),
  meetings: (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <rect x="2.25" y="3.25" width="11.5" height="10.5" rx="1.5" />
      <path d="M2.25 6.5h11.5M5.5 1.75v3M10.5 1.75v3" />
    </svg>
  ),
  ideas: (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 1.75a4.25 4.25 0 0 0-2.5 7.7v1.3h5v-1.3A4.25 4.25 0 0 0 8 1.75Z" />
      <path d="M6.5 13.25h3" />
    </svg>
  ),
  bottlenecks: (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path d="M2.5 13.25h11M4.5 13.25V8M8 13.25V3.5M11.5 13.25v-3.5" />
    </svg>
  ),
};

const NAV = [
  { id: "repositories", label: "Repositories" },
  { id: "meetings", label: "Meetings" },
  { id: "ideas", label: "Ideas" },
  { id: "bottlenecks", label: "Bottleneck map" },
];

export default function Sidebar({ view, onNavigate, counts, online, user, onLogout }) {
  const [currentUser, setCurrentUser] = useState(user || null);

  useEffect(() => {
    if (user !== undefined) {
      setCurrentUser(user);
    }
  }, [user]);

  useEffect(() => {
    const unsubscribe = onAuthChanged((authUser) => {
      setCurrentUser(authUser);
    });
    return () => unsubscribe();
  }, []);

  async function handleGoogleLogin() {
    try {
      const loggedUser = await loginWithGoogle();
      setCurrentUser(loggedUser);
    } catch (err) {
      console.warn("Google sign-in cancelled or failed:", err);
    }
  }

  async function handleLogout() {
    try {
      await logoutUser();
      setCurrentUser(null);
      if (onLogout) onLogout();
    } catch (err) {
      console.warn("Logout failed:", err);
    }
  }

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">t</span>
        <div className="brand-text">
          <span className="brand-name">tryout</span>
          <span className="brand-tag">Future of work prototype</span>
        </div>
      </div>

      {currentUser && <WorkspaceSwitcher onOpenSettings={() => onNavigate("settings")} />}

      <nav className="nav">
        <p className="nav-label">Pages</p>
        {NAV.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            className="nav-item"
            aria-current={view === id ? "page" : undefined}
            onClick={() => onNavigate(id)}
          >
            {ICONS[id]}
            {label}
            {counts[id] > 0 && (
              <span className={`nav-count${id === "ideas" ? " is-alert" : ""}`}>
                {counts[id]}
              </span>
            )}
          </button>
        ))}
      </nav>

      <div className="sidebar-auth">
        {currentUser ? (
          <div className="sidebar-user">
            {currentUser.photoURL ? (
              <img src={currentUser.photoURL} alt="" className="avatar" />
            ) : (
              <div className="avatar avatar-fallback">
                {(currentUser.displayName || currentUser.email || "U")[0].toUpperCase()}
              </div>
            )}
            <div className="user-details">
              <span className="user-name" title={currentUser.displayName || currentUser.email}>
                {currentUser.displayName || currentUser.email}
              </span>
              <button type="button" className="btn-signout" onClick={handleLogout}>
                Sign out
              </button>
            </div>
          </div>
        ) : (
          <button type="button" className="btn-google-signin" onClick={handleGoogleLogin}>
            <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
              <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.8-2.4 3.65v3h3.86c2.26-2.09 3.68-5.17 3.68-9.09z"/>
              <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.26 21.3 7.37 24 12 24z"/>
              <path fill="#FBBC05" d="M5.27 14.29c-.25-.72-.38-1.49-.38-2.29s.13-1.57.38-2.29V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.98-3.09z"/>
              <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.37 0 3.26 2.7 1.29 6.62l3.98 3.09c.95-2.85 3.6-4.96 6.73-4.96z"/>
            </svg>
            Sign in with Google
          </button>
        )}
      </div>

      <div className="sidebar-foot">
        <span
          className={`dot ${online === null ? "" : online ? "is-up" : "is-down"}`}
        />
        <span>
          {online === null ? "Connecting…" : online ? "API connected" : "API unreachable"}
        </span>
      </div>
    </aside>
  );
}
