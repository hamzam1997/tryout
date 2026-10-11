/** Shared display helpers for dates, times, and short labels. */

const DATE_MED = {
  day: "numeric",
  month: "short",
  year: "numeric",
};

const DATE_TIME = {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
};

export function formatDate(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, DATE_MED);
}

export function formatDateTime(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString(undefined, DATE_TIME);
}

/** Compact relative label, e.g. "just now", "3h ago", falling back to a date. */
export function formatRelative(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;

  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  const future = seconds < 0;
  const abs = Math.abs(seconds);

  if (abs < 45) return "just now";
  if (abs < 90) return future ? "in 1m" : "1m ago";

  const minutes = Math.round(abs / 60);
  if (minutes < 60) return future ? `in ${minutes}m` : `${minutes}m ago`;

  const hours = Math.round(minutes / 60);
  if (hours < 36) return future ? `in ${hours}h` : `${hours}h ago`;

  const days = Math.round(hours / 24);
  if (days < 14) return future ? `in ${days}d` : `${days}d ago`;

  return formatDate(value);
}

export function formatSource(source) {
  if (!source) return "";
  const labels = {
    UPLOAD: "Upload",
    SEED: "Demo",
    MEET: "Meet",
    ZOOM: "Zoom",
    TEAMS: "Teams",
  };
  return labels[source] || source;
}

export function formatPriority(priority) {
  if (!priority) return null;
  const key = String(priority).toLowerCase();
  const labels = { high: "High", medium: "Medium", low: "Low" };
  return labels[key] || priority;
}

const FRICTION_LABELS = {
  EXTERNAL_SERVICE_DEPENDENCY: "External service",
  AUTH_CREDENTIAL_REQUIRED: "Credentials / auth",
  SCHEMA_MIGRATION_REQUIRED: "Schema migration",
  CROSS_TEAM_CONTRACT: "Cross-team contract",
  PRODUCT_DECISION: "Product decision",
};

export function formatFrictionCategory(category) {
  return FRICTION_LABELS[category] || category;
}
