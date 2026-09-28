const STORAGE_KEY = "tryout.approver";

export function getStoredApprover() {
  try {
    return (localStorage.getItem(STORAGE_KEY) || "").trim();
  } catch {
    return "";
  }
}

export function setStoredApprover(name) {
  const value = (name || "").trim();
  try {
    if (value) localStorage.setItem(STORAGE_KEY, value);
  } catch {
    // ignore quota / private mode
  }
  return value;
}
