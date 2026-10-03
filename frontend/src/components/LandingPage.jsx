import { useState } from "react";
import { loginWithGitHub, loginWithGoogle } from "../lib/firebase";

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
      <div className="landing-ambient-glow" aria-hidden="true" />
      
      <div className="landing-container">
        {/* Brand header */}
        <div className="landing-brand">
          <div className="landing-logo">t</div>
          <span className="landing-brand-name">tryout</span>
          <span className="landing-badge">Next-Gen Workspace</span>
        </div>

        {/* Hero */}
        <div className="landing-hero">
          <h1 className="landing-title">
            Turn team discussions into <br />
            <span className="landing-gradient-text">verified production code.</span>
          </h1>
          <p className="landing-subtitle">
            Autonomous repository onboarding, real-time meeting idea extraction, 
            and self-verifying implementation pipelines backed by Google Cloud & Firestore.
          </p>
        </div>

        {/* Auth Card */}
        <div className="landing-card">
          <h2 className="landing-card-title">Sign in to your workspace</h2>
          <p className="landing-card-desc">
            Connect using your company Google account or GitHub credentials.
          </p>

          {error && (
            <div className="landing-error" role="alert">
              <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor">
                <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 1.5a5.5 5.5 0 1 1 0 11 5.5 5.5 0 0 1 0-11zm-.75 2.75v4.5a.75.75 0 0 0 1.5 0v-4.5a.75.75 0 0 0-1.5 0zm.75 7.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2z" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          <div className="landing-actions">
            <button
              type="button"
              className="landing-btn landing-btn-github"
              onClick={handleGitHubLogin}
              disabled={loadingGitHub || loadingGoogle}
            >
              <svg viewBox="0 0 16 16" width="18" height="18" fill="currentColor" aria-hidden="true">
                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
              </svg>
              <span>{loadingGitHub ? "Connecting..." : "Continue with GitHub"}</span>
            </button>

            <button
              type="button"
              className="landing-btn landing-btn-google"
              onClick={handleGoogleLogin}
              disabled={loadingGoogle || loadingGitHub}
            >
              <svg viewBox="0 0 18 18" width="18" height="18" aria-hidden="true">
                <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.616z" />
                <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" />
                <path fill="#FBBC05" d="M3.964 10.707c-.18-.54-.282-1.117-.282-1.707s.102-1.167.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z" />
                <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.961L3.964 7.293C4.672 5.166 6.656 3.58 9 3.58z" />
              </svg>
              <span>{loadingGoogle ? "Connecting..." : "Continue with Google"}</span>
            </button>
          </div>

          <div className="landing-footer-note">
            <span>By signing in, your session is securely persisted for this browser session.</span>
          </div>
        </div>

        {/* Feature Grid Highlights */}
        <div className="landing-features">
          <div className="landing-feature-item">
            <span className="landing-feature-icon">⚡</span>
            <h3>Deep Onboarding</h3>
            <p>Scans codebases to catalog architectural boundaries, APIs, and frameworks.</p>
          </div>
          <div className="landing-feature-item">
            <span className="landing-feature-icon">💡</span>
            <h3>Meeting Insights</h3>
            <p>Extracts actionable implementation ideas directly from meeting transcripts.</p>
          </div>
          <div className="landing-feature-item">
            <span className="landing-feature-icon">🛡️</span>
            <h3>Continuous Proof</h3>
            <p>Synthesizes tests and runs sandboxed attempts before any code is merged.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
