import { initializeApp, getApps } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  GithubAuthProvider,
  signInWithPopup,
  signOut,
  onAuthStateChanged,
  setPersistence,
  browserSessionPersistence,
} from "firebase/auth";

let authInstance = null;
let googleProviderInstance = null;
let githubProviderInstance = null;
let initPromise = null;

const SESSION_EXPIRY_MS = 2 * 60 * 60 * 1000; // 2 hours
const SESSION_TIMESTAMP_KEY = "tryout_session_login_time";

/**
 * Fetch Firebase client configuration dynamically from server runtime.
 * Never hardcodes keys, project IDs, or secrets in client source code.
 */
async function fetchServerConfig() {
  const resp = await fetch("/api/auth/firebase-config");
  if (!resp.ok) {
    throw new Error(`Failed to load Firebase configuration (${resp.status})`);
  }
  return resp.json();
}

/**
 * Initialize Firebase dynamically from backend configuration.
 */
export async function getFirebaseAuth() {
  if (authInstance) {
    return {
      auth: authInstance,
      googleProvider: googleProviderInstance,
      githubProvider: githubProviderInstance,
    };
  }

  if (initPromise) {
    return initPromise;
  }

  initPromise = (async () => {
    try {
      const config = await fetchServerConfig();
      const apps = getApps();
      const app = apps.length > 0 ? apps[0] : initializeApp(config);
      authInstance = getAuth(app);

      // Set session persistence to browser session only (closes on tab/window close)
      await setPersistence(authInstance, browserSessionPersistence).catch(() => {});

      googleProviderInstance = new GoogleAuthProvider();
      githubProviderInstance = new GithubAuthProvider();
      githubProviderInstance.addScope("repo");
      githubProviderInstance.addScope("read:user");

      return {
        auth: authInstance,
        googleProvider: googleProviderInstance,
        githubProvider: githubProviderInstance,
      };
    } catch (err) {
      console.error("Failed to initialize Firebase Auth:", err);
      initPromise = null;
      throw err;
    }
  })();

  return initPromise;
}

/**
 * Check if the current session has exceeded its maximum duration.
 */
export function checkSessionExpired() {
  const loginTime = sessionStorage.getItem(SESSION_TIMESTAMP_KEY);
  if (!loginTime) return false;
  const elapsed = Date.now() - parseInt(loginTime, 10);
  return elapsed > SESSION_EXPIRY_MS;
}

/**
 * Stamp current login time.
 */
function stampSessionTime() {
  sessionStorage.setItem(SESSION_TIMESTAMP_KEY, Date.now().toString());
}

/**
 * Sign in using Google OAuth via Firebase.
 */
export async function loginWithGoogle() {
  const { auth, googleProvider } = await getFirebaseAuth();
  const result = await signInWithPopup(auth, googleProvider);
  const user = result.user;
  stampSessionTime();

  // Sync session and persist user with Flask backend & Firestore
  await fetch("/api/auth/firebase-sync", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user: {
        uid: user.uid,
        email: user.email,
        name: user.displayName || user.email,
        avatar_url: user.photoURL,
      },
    }),
  });

  return user;
}

/**
 * Sign in using GitHub OAuth via Firebase.
 * Automatically obtains the GitHub OAuth Access Token so repository onboarding
 * works immediately without separate OAuth authorization.
 */
export async function loginWithGitHub() {
  const { auth, githubProvider } = await getFirebaseAuth();
  const result = await signInWithPopup(auth, githubProvider);
  const credential = GithubAuthProvider.credentialFromResult(result);
  const githubToken = credential?.accessToken;
  const user = result.user;
  stampSessionTime();

  // Sync GitHub token and persist user with Flask backend & Firestore
  const syncResp = await fetch("/api/auth/firebase-sync", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      github_token: githubToken,
      user: {
        uid: user.uid,
        email: user.email,
        name: user.displayName || user.email,
        avatar_url: user.photoURL,
      },
    }),
  });

  const syncData = await syncResp.json().catch(() => ({}));
  return { user, githubToken, syncData };
}

/**
 * Log out from Firebase and clear the Flask session and local session storage.
 */
export async function logoutUser() {
  sessionStorage.removeItem(SESSION_TIMESTAMP_KEY);
  try {
    const { auth } = await getFirebaseAuth();
    await signOut(auth).catch(() => {});
  } catch (err) {
    console.warn("Firebase signOut error:", err);
  }
  await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
  await fetch("/api/auth/github/logout", { method: "POST" }).catch(() => {});
}

/**
 * Subscribe to auth state changes with automatic session expiry enforcement.
 */
export function onAuthChanged(callback) {
  let unsubscribeAuth = null;
  getFirebaseAuth()
    .then(({ auth }) => {
      unsubscribeAuth = onAuthStateChanged(auth, (user) => {
        if (user && checkSessionExpired()) {
          logoutUser().then(() => callback(null));
          return;
        }
        callback(user);
      });
    })
    .catch((err) => {
      console.warn("Firebase Auth listener initialization error:", err);
      callback(null);
    });

  return () => {
    if (unsubscribeAuth) unsubscribeAuth();
  };
}
