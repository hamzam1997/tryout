import { initializeApp, getApps } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  GithubAuthProvider,
  signInWithPopup,
  signOut,
  onAuthStateChanged,
  setPersistence,
  browserLocalPersistence,
} from "firebase/auth";

let authInstance = null;
let googleProviderInstance = null;
let githubProviderInstance = null;
let initPromise = null;

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

      // Stay signed in across tabs and browser restarts until the user signs out.
      await setPersistence(authInstance, browserLocalPersistence).catch(() => {});

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
 * Create (or refresh) the Flask session for a Firebase user.
 */
let syncInFlight = null;

async function syncSession(user, githubToken) {
  // Sign-in and onAuthStateChanged both sync; never run two at once. A call carrying a
  // GitHub token waits its turn instead of joining, so the token is never dropped.
  if (githubToken || !syncInFlight) {
    const previous = syncInFlight;
    syncInFlight = (async () => {
      await previous?.catch(() => {});
      // The server verifies the ID token and takes the user's identity from it.
      return fetch("/api/auth/firebase-sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: await user.getIdToken(), github_token: githubToken }),
      });
    })();
    const mine = syncInFlight;
    mine.finally(() => {
      if (syncInFlight === mine) syncInFlight = null;
    }).catch(() => {});
  }
  return (await syncInFlight).clone();
}

/**
 * Sign in using Google OAuth via Firebase.
 */
export async function loginWithGoogle() {
  const { auth, googleProvider } = await getFirebaseAuth();
  const result = await signInWithPopup(auth, googleProvider);
  await syncSession(result.user);
  return result.user;
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

  const syncResp = await syncSession(user, githubToken);

  const syncData = await syncResp.json().catch(() => ({}));
  return { user, githubToken, syncData };
}

/**
 * Log out from Firebase and clear the Flask session and local session storage.
 */
export async function logoutUser() {
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
 * Subscribe to auth state changes. A user restored from a previous visit gets a
 * fresh server session if the old one is gone.
 */
export function onAuthChanged(callback) {
  let unsubscribeAuth = null;
  getFirebaseAuth()
    .then(({ auth }) => {
      unsubscribeAuth = onAuthStateChanged(auth, async (user) => {
        if (user) {
          const me = await fetch("/api/auth/me").catch(() => null);
          if (!me?.ok) await syncSession(user).catch(() => {});
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
