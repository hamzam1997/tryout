import { useCallback, useEffect, useState } from "react";

// URL <-> page state. Flat pages, so history.pushState is enough; no router dependency.
const PAGES = ["repositories", "meetings", "ideas", "bottlenecks", "settings"];

export function parseRoute({ pathname, search }) {
  const [first, second] = pathname.split("/").filter(Boolean);
  if (first === "attempts" && Number(second)) return { view: "report", attemptId: Number(second) };
  const status = new URLSearchParams(search).get("status");
  if (first === "ideas") return { view: "ideas", status: status || "PENDING" };
  return { view: PAGES.includes(first) ? first : "repositories" };
}

export function routePath({ view, attemptId, status }) {
  if (view === "report") return `/attempts/${attemptId}`;
  if (view === "ideas" && status && status !== "PENDING") return `/ideas?status=${status}`;
  return `/${view}`;
}

export function useRoute() {
  const [route, setRoute] = useState(() => parseRoute(window.location));

  useEffect(() => {
    const onPop = () => setRoute(parseRoute(window.location));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((next, { replace = false } = {}) => {
    const path = routePath(next);
    if (path !== window.location.pathname + window.location.search) {
      window.history[replace ? "replaceState" : "pushState"](null, "", path);
    }
    setRoute(parseRoute(window.location));
  }, []);

  return [route, navigate];
}
