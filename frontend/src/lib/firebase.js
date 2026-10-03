import { initializeApp } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  GithubAuthProvider,
  signInWithPopup,
  signOut,
  onAuthStateChanged,
} from "firebase/auth";

// Vite client env variables or fallback configuration
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyCAst4nJNYaxCp_h5-C0D0e2QSh6mDi6y0",
  authDomain:
    import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "project-d8ffc1c1-61f2-4aef-9ab.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "project-d8ffc1c1-61f2-4aef-9ab",
  storageBucket:
    import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "project-d8ffc1c1-61f2-4aef-9ab.firebasestorage.app",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "228085742413",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:228085742413:web:80180bf01b38db40acd504",
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

// Google Provider
export const googleProvider = new GoogleAuthProvider();

// GitHub Provider with repository access scopes
export const githubProvider = new GithubAuthProvider();
githubProvider.addScope("repo");
githubProvider.addScope("read:user");

/**
 * Sign in using Google OAuth via Firebase.
 */
export async function loginWithGoogle() {
  const result = await signInWithPopup(auth, googleProvider);
  const user = result.user;

  // Sync session with Flask backend
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
  const result = await signInWithPopup(auth, githubProvider);
  const credential = GithubAuthProvider.credentialFromResult(result);
  const githubToken = credential?.accessToken;
  const user = result.user;

  // Sync GitHub token with Flask backend
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
 * Log out from Firebase and clear the Flask session.
 */
export async function logoutUser() {
  await signOut(auth).catch(() => {});
  await fetch("/api/auth/github/logout", { method: "POST" }).catch(() => {});
}

/**
 * Subscribe to auth state changes.
 */
export function onAuthChanged(callback) {
  return onAuthStateChanged(auth, callback);
}
