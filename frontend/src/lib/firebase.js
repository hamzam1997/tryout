import { initializeApp, getApps } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  GithubAuthProvider,
  signInWithPopup,
  linkWithPopup,
  reauthenticateWithPopup,
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
 * Fetch the Firebase web config from the server, which reads it from FIREBASE_* env vars.
 * These values are public by design (they ship to every browser); they just aren't in the repo.
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
      // Sign-in asks for no extra scopes (public profile only). Repo access is
      // requested only when the user connects GitHub for repositories.
      githubProviderInstance = new GithubAuthProvider();

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
  const resp = (await syncInFlight).clone();
  // No server session means every /api call 401s and bounces back to the landing page
  // with no message; fail the sign-in here so the user sees why.
  if (!resp.ok) {
    const body = await resp.clone().json().catch(() => ({}));
    throw new Error(body.error || `Sign-in failed on the server (${resp.status}).`);
  }
  return resp;
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
 * Sign in using GitHub OAuth via Firebase. `repoAccess` adds the `repo` scope, for
 * the repository connect step only; plain sign-in requests no scopes.
 */
export async function loginWithGitHub({ repoAccess = false } = {}) {
  const { auth, githubProvider } = await getFirebaseAuth();
  let provider = githubProvider;
  if (repoAccess) {
    provider = new GithubAuthProvider();
    provider.addScope("repo");
  }
  // Connecting while signed in must keep the current identity: a Google user
  // links GitHub, a GitHub user re-authorizes with the wider scope. A plain
  // sign-in popup would switch accounts and lose their workspace.
  const current = repoAccess ? auth.currentUser : null;
  const hasGitHub = current?.providerData.some((p) => p.providerId === GithubAuthProvider.PROVIDER_ID);
  const result = !current
    ? await signInWithPopup(auth, provider)
    : hasGitHub
      ? await reauthenticateWithPopup(current, provider)
      : await linkWithPopup(current, provider);
  const credential = GithubAuthProvider.credentialFromResult(result);
  const githubToken = credential?.accessToken;
  const user = result.user;

  const syncResp = await syncSession(user, githubToken);

  const syncData = await syncResp.json().catch(() => ({}));
  return { user, githubToken, syncData };
}

// Set while this browser holds an evaluator session, so signed-out visitors don't
// probe /api/auth/me (a 401 in their console) on every page load.
const EVALUATOR_KEY = "tryout.evaluator";

/** An evaluator, shaped like the Firebase user the UI reads; null for anyone else. */
function asEvaluator(user) {
  return user?.provider === "evaluator"
    ? { uid: user.uid, displayName: user.name, email: null, photoURL: null, isEvaluator: true }
    : null;
}

/** Whether the server offers "Continue as evaluator". */
export async function evaluatorLoginEnabled() {
  const config = await fetchServerConfig().catch(() => null);
  return Boolean(config?.evaluatorLogin);
}

/**
 * Sign in as a throwaway evaluator: no Google or GitHub account. The server creates
 * the evaluator and a workspace seeded with demo history.
 */
export async function loginAsEvaluator() {
  const resp = await fetch("/api/auth/evaluator", { method: "POST" });
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(body.error || `Evaluator sign-in failed (${resp.status}).`);
  }
  localStorage.setItem(EVALUATOR_KEY, "1");
  return asEvaluator(body.user);
}

/** The evaluator this browser is still signed in as, if any. */
async function restoreEvaluator() {
  if (!localStorage.getItem(EVALUATOR_KEY)) return null;
  const me = await fetch("/api/auth/me").then((r) => (r.ok ? r.json() : null)).catch(() => null);
  const evaluator = asEvaluator(me?.user);
  if (!evaluator) localStorage.removeItem(EVALUATOR_KEY);
  return evaluator;
}

/**
 * Log out from Firebase and clear the Flask session and local session storage.
 */
export async function logoutUser() {
  localStorage.removeItem(EVALUATOR_KEY);
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
        if (!user) return callback(await restoreEvaluator());
        const me = await fetch("/api/auth/me").catch(() => null);
        if (!me?.ok && !(await syncSession(user).then(() => true, () => false))) {
          return callback(null); // signed in to Firebase but not to the server
        }
        callback(user);
      });
    })
    .catch(async (err) => {
      console.warn("Firebase Auth listener initialization error:", err);
      // Evaluators don't use Firebase, so they can still get in.
      callback(await restoreEvaluator());
    });

  return () => {
    if (unsubscribeAuth) unsubscribeAuth();
  };
}
