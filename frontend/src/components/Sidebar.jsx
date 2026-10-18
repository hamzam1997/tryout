import { useEffect, useState } from "react";
import { loginWithGoogle, logoutUser, onAuthChanged } from "../lib/firebase";
import Icon, { Avatar, Logo } from "./Icon";
import WorkspaceSwitcher from "./WorkspaceSwitcher";

const NAV = [
  { id: "repositories", label: "Repositories" },
  { id: "meetings", label: "Meetings" },
  { id: "ideas", label: "Ideas" },
  { id: "bottlenecks", label: "Bottleneck map" },
];

export default function Sidebar({ view, onNavigate, counts, online, user, onLogout, tourSlot }) {
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

  const displayName = currentUser?.displayName || currentUser?.email;

  return (
    <aside className="sidebar">
      <div className="brand">
        <Logo size={28} />
        <span className="brand-name">tryout</span>
      </div>

      {currentUser && <WorkspaceSwitcher />}

      <nav className="nav" aria-label="Pages">
        {NAV.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            className="nav-item"
            data-tour={`nav-${id}`}
            aria-current={view === id ? "page" : undefined}
            onClick={() => onNavigate(id)}
          >
            <Icon name={id} />
            <span className="nav-text">{label}</span>
            {counts[id] > 0 && (
              <span className={`nav-count${id === "ideas" ? " is-alert" : ""}`}>
                {counts[id]}
              </span>
            )}
          </button>
        ))}
        {currentUser && (
          <button
            type="button"
            className="nav-item nav-item-settings"
            aria-current={view === "settings" ? "page" : undefined}
            onClick={() => onNavigate("settings")}
          >
            <Icon name="settings" />
            <span className="nav-text">Settings</span>
          </button>
        )}
      </nav>

      {tourSlot}

      <div className="sidebar-foot">
        {currentUser ? (
          <div className="sidebar-user">
            <Avatar name={displayName} src={currentUser.photoURL} size={28} />
            <div className="user-details">
              <span className="user-name" title={displayName}>{displayName}</span>
              <span className="api-status">
                <span className={`dot ${online === null ? "" : online ? "is-up" : "is-down"}`} />
                {online === null ? "Connecting…" : online ? "API connected" : "API unreachable"}
              </span>
            </div>
            <button
              type="button"
              className="icon-btn"
              onClick={handleLogout}
              aria-label="Sign out"
              title="Sign out"
            >
              <Icon name="signout" />
            </button>
          </div>
        ) : (
          <button type="button" className="btn btn-secondary btn-block" onClick={handleGoogleLogin}>
            Sign in with Google
          </button>
        )}
      </div>
    </aside>
  );
}
