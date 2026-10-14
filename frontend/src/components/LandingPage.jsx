import { useState } from "react";
import { loginWithGitHub, loginWithGoogle } from "../lib/firebase";
import Icon, { Logo } from "./Icon";

export default function LandingPage({ onLoginSuccess }) {
  const [loadingGoogle, setLoadingGoogle] = useState(false);
  const [loadingGitHub, setLoadingGitHub] = useState(false);
  const [error, setError] = useState("");

  async function handleGoogleLogin() {
    setError("");
    setLoadingGoogle(true);
    try {
      const user = await loginWithGoogle();
      if (user && onLoginSuccess) {
        onLoginSuccess(user);
      }
    } catch (err) {
      console.error("Google login failed:", err);
      if (err.code !== "auth/popup-closed-by-user") {
        setError(err.message || "Failed to sign in with Google.");
      }
    } finally {
      setLoadingGoogle(false);
    }
  }

  async function handleGitHubLogin() {
    setError("");
    setLoadingGitHub(true);
    try {
      const result = await loginWithGitHub();
      if (result?.user && onLoginSuccess) {
        onLoginSuccess(result.user);
      }
    } catch (err) {
      console.error("GitHub login failed:", err);
      if (err.code !== "auth/popup-closed-by-user") {
        setError(err.message || "Failed to sign in with GitHub.");
      }
    } finally {
      setLoadingGitHub(false);
    }
  }

  return (
    <div className="landing-wrap">
      <div className="landing-container">
        <section className="landing-hero">
          <div className="landing-brand">
            <Logo size={32} />
            <span className="landing-brand-name">tryout</span>
          </div>
          <h1 className="landing-title">Meeting ideas, shipped as reviewed pull requests.</h1>
          <p className="landing-subtitle">
            tryout reads your meeting transcripts, grounds each idea in your codebase,
            and runs a sandboxed attempt you can review before anything merges.
          </p>
          <ul className="landing-features">
            <li className="landing-feature-item">
              <span className="landing-feature-icon"><Icon name="layers" /></span>
              <div>
                <h3>Repository catalog</h3>
                <p>Maps modules, routes, models and owners so every idea lands on real code.</p>
              </div>
            </li>
            <li className="landing-feature-item">
              <span className="landing-feature-icon"><Icon name="ideas" /></span>
              <div>
                <h3>Ideas from meetings</h3>
                <p>Pulls actionable proposals out of Meet, Zoom and Teams transcripts.</p>
              </div>
            </li>
            <li className="landing-feature-item">
              <span className="landing-feature-icon"><Icon name="shield" /></span>
              <div>
                <h3>Proof before merge</h3>
                <p>Writes the change, mocks what it can't reach and runs the tests.</p>
              </div>
            </li>
          </ul>
        </section>

        <section className="landing-card" aria-labelledby="signin-title">
          <h2 id="signin-title" className="landing-card-title">Sign in</h2>
          <p className="landing-card-desc">Use your work Google account or GitHub.</p>

          {error && (
            <div className="alert alert-error" role="alert">
              <span>{error}</span>
            </div>
          )}

          <div className="landing-actions">
            <button
              type="button"
              className="btn btn-dark btn-lg btn-block"
              onClick={handleGitHubLogin}
              disabled={loadingGitHub || loadingGoogle}
            >
              <svg viewBox="0 0 16 16" width="18" height="18" fill="currentColor" aria-hidden="true">
                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
              </svg>
              <span>{loadingGitHub ? "Connecting…" : "Continue with GitHub"}</span>
            </button>

            <button
              type="button"
              className="btn btn-secondary btn-lg btn-block btn-neutral"
              onClick={handleGoogleLogin}
              disabled={loadingGoogle || loadingGitHub}
            >
              <svg viewBox="0 0 18 18" width="18" height="18" aria-hidden="true">
                <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.616z" />
                <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" />
                <path fill="#FBBC05" d="M3.964 10.707c-.18-.54-.282-1.117-.282-1.707s.102-1.167.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z" />
                <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.961L3.964 7.293C4.672 5.166 6.656 3.58 9 3.58z" />
              </svg>
              <span>{loadingGoogle ? "Connecting…" : "Continue with Google"}</span>
            </button>
          </div>

          <p className="landing-footer-note">
            GitHub sign-in also connects your repositories for onboarding.
          </p>
        </section>
      </div>
    </div>
  );
}
