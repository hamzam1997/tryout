// Vite proxies these to the Flask app in dev; same-origin in production.

import { logoutUser } from "./lib/firebase";

async function parse(response) {
  // The server session is gone: sign out so the app shows the login page.
  if (response.status === 401) logoutUser();
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error || `Request failed (${response.status})`);
  }
  return body;
}

// Meetings API
export function listMeetings() {
  return fetch("/api/meetings").then(parse);
}

export function getMeeting(id) {
  return fetch(`/api/meetings/${id}`).then(parse);
}

export function deleteMeeting(id) {
  return fetch(`/api/meetings/${id}`, { method: "DELETE" }).then(async (response) => {
    if (response.status === 204) return true;
    return parse(response);
  });
}

export function uploadTranscript({ file, title, occurredAt }) {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);
  if (occurredAt) form.append("occurred_at", new Date(occurredAt).toISOString());

  return fetch("/api/meetings/upload", { method: "POST", body: form }).then(parse);
}

export async function extractIdeas(meetingId) {
  const response = await fetch(`/api/meetings/${meetingId}/extract-ideas`, { method: "POST" });
  const body = await response.json().catch(() => ({}));
  // 202 = queued in background; still a success for the client.
  if (!response.ok && response.status !== 202) {
    const error = new Error(
      body.ideas_error || body.error || `Request failed (${response.status})`
    );
    error.payload = body;
    throw error;
  }
  return body;
}

export function loadDemoMeeting() {
  return fetch("/api/meetings/demo", { method: "POST" }).then(parse);
}

// Ideas API
export function listIdeas(status) {
  const query = status && status !== "ALL" ? `?status=${encodeURIComponent(status)}` : "";
  return fetch(`/api/ideas${query}`).then(parse);
}

export function getIdea(id) {
  return fetch(`/api/ideas/${id}`).then(parse);
}

export function getIdeaCounts() {
  return fetch("/api/ideas/counts").then(parse);
}

export function approveIdea(id, repositoryId) {
  return fetch(`/api/ideas/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repository_id: repositoryId }),
  }).then(parse);
}

export function retryIdeaAttempt(id) {
  return fetch(`/api/ideas/${id}/attempts/retry`, { method: "POST" }).then(parse);
}

export function rejectIdea(id) {
  return fetch(`/api/ideas/${id}/reject`, { method: "POST" }).then(parse);
}

export function deleteIdea(id) {
  return fetch(`/api/ideas/${id}`, { method: "DELETE" }).then(async (response) => {
    if (response.status === 204) return true;
    return parse(response);
  });
}

// Repositories API
export function listRepositories() {
  return fetch("/api/repositories").then(parse);
}

export function getRepository(id) {
  return fetch(`/api/repositories/${id}`).then(parse);
}

export function getRepositoryCatalog(id) {
  return fetch(`/api/repositories/${id}/catalog`).then(parse);
}

export function deleteRepository(id) {
  return fetch(`/api/repositories/${id}`, { method: "DELETE" }).then(parse);
}

export function onboardRepository({ sourceType, repoFullName, branch, path, forceRefresh }) {
  const payload = {
    source_type: sourceType,
    repo_full_name: repoFullName,
    branch: branch,
    path: path,
    force_refresh: forceRefresh,
  };
  return fetch("/api/repositories/onboard", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then(parse);
}

// GitHub Auth API
export function getGithubAuthStatus() {
  return fetch("/api/auth/github/status").then(parse);
}

export function getGithubRepos() {
  return fetch("/api/auth/github/repos").then(parse);
}

export function logoutGithub() {
  return fetch("/api/auth/github/logout", { method: "POST" }).then(parse);
}

export function health() {
  return fetch("/health").then((r) => r.ok);
}

// Bottleneck map
export function getBottlenecks() {
  return fetch("/api/bottlenecks").then(parse);
}

export function getAttempt(id) {
  return fetch(`/api/attempts/${id}`).then(parse);
}

// Workspaces
export function listWorkspaces() {
  return fetch("/api/workspaces").then(parse);
}

export function createWorkspace(name) {
  return fetch("/api/workspaces", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  }).then(parse);
}

export function switchWorkspace(id) {
  return fetch(`/api/workspaces/${id}/switch`, { method: "POST" }).then(parse);
}

export function renameWorkspace(id, name) {
  return fetch(`/api/workspaces/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  }).then(parse);
}

export function deleteWorkspace(id) {
  return fetch(`/api/workspaces/${id}`, { method: "DELETE" }).then(async (response) => {
    if (response.status === 204) return true;
    return parse(response);
  });
}

// Invitations
export function listInvitations(workspaceId) {
  return fetch(`/api/workspaces/${workspaceId}/invitations`).then(parse);
}

export function createInvitation(workspaceId, email, role) {
  return fetch(`/api/workspaces/${workspaceId}/invitations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, role }),
  }).then(parse);
}

export function revokeInvitation(workspaceId, token) {
  return fetch(`/api/workspaces/${workspaceId}/invitations/${token}`, { method: "DELETE" }).then(
    async (response) => (response.status === 204 ? true : parse(response))
  );
}

export function getInvitation(token) {
  return fetch(`/api/invitations/${encodeURIComponent(token)}`).then(parse);
}

export function acceptInvitation(token) {
  return fetch(`/api/invitations/${encodeURIComponent(token)}/accept`, { method: "POST" }).then(parse);
}

// Members
export function listMembers(workspaceId) {
  return fetch(`/api/workspaces/${workspaceId}/members`).then(parse);
}

export function changeMemberRole(workspaceId, uid, role) {
  return fetch(`/api/workspaces/${workspaceId}/members/${encodeURIComponent(uid)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role }),
  }).then(parse);
}

export function removeMember(workspaceId, uid) {
  return fetch(`/api/workspaces/${workspaceId}/members/${encodeURIComponent(uid)}`, { method: "DELETE" }).then(
    async (response) => (response.status === 204 ? true : parse(response))
  );
}

// Workspace GitHub connection
export function getWorkspaceGitHub(workspaceId) {
  return fetch(`/api/workspaces/${workspaceId}/github`).then(parse);
}

export function connectWorkspaceGitHub(workspaceId) {
  return fetch(`/api/workspaces/${workspaceId}/github`, { method: "POST" }).then(parse);
}

export function disconnectWorkspaceGitHub(workspaceId) {
  return fetch(`/api/workspaces/${workspaceId}/github`, { method: "DELETE" }).then(
    async (response) => (response.status === 204 ? true : parse(response))
  );
}
