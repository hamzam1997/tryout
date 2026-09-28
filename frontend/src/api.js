// Vite proxies these to the Flask app in dev; same-origin in production.

async function parse(response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error || `Request failed (${response.status})`);
  }
  return body;
}

// Meetings API
export function listMeetings() {
  return fetch("/meetings").then(parse);
}

export function getMeeting(id) {
  return fetch(`/meetings/${id}`).then(parse);
}

export function uploadTranscript({ file, title, occurredAt }) {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);
  if (occurredAt) form.append("occurred_at", new Date(occurredAt).toISOString());

  return fetch("/meetings/upload", { method: "POST", body: form }).then(parse);
}

export async function extractIdeas(meetingId) {
  const response = await fetch(`/meetings/${meetingId}/extract-ideas`, { method: "POST" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(
      body.ideas_error || body.error || `Request failed (${response.status})`
    );
    error.payload = body;
    throw error;
  }
  return body;
}

export function loadDemoMeeting() {
  return fetch("/meetings/demo", { method: "POST" }).then(parse);
}

// Ideas API
export function listIdeas(status) {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return fetch(`/ideas${query}`).then(parse);
}

export function approveIdea(id, approvedBy = "local") {
  return fetch(`/ideas/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved_by: approvedBy }),
  }).then(parse);
}

export function rejectIdea(id) {
  return fetch(`/ideas/${id}/reject`, { method: "POST" }).then(parse);
}

// Repositories API
export function listRepositories() {
  return fetch("/repositories").then(parse);
}

export function getRepository(id) {
  return fetch(`/repositories/${id}`).then(parse);
}

export function getRepositoryCatalog(id) {
  return fetch(`/repositories/${id}/catalog`).then(parse);
}

export function onboardRepository({ sourceType, repoFullName, branch, path, forceRefresh }) {
  const payload = {
    source_type: sourceType,
    repo_full_name: repoFullName,
    branch: branch,
    path: path,
    force_refresh: forceRefresh,
  };
  return fetch("/repositories/onboard", {
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
