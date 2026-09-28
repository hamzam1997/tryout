// Vite proxies these to the Flask app in dev; same-origin in production.

async function parse(response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error || `Request failed (${response.status})`);
  }
  return body;
}

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

export function health() {
  return fetch("/").then((r) => r.ok);
}
