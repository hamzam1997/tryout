// Run: npm test
import assert from "node:assert/strict";
import { parseRoute, routePath } from "./route.js";

const loc = (url) => {
  const u = new URL(url, "http://x");
  return { pathname: u.pathname, search: u.search };
};

assert.deepEqual(parseRoute(loc("/attempts/42")), { view: "report", attemptId: 42 });
assert.deepEqual(parseRoute(loc("/ideas?status=DONE")), { view: "ideas", status: "DONE" });
assert.deepEqual(parseRoute(loc("/ideas")), { view: "ideas", status: "PENDING" });
assert.deepEqual(parseRoute(loc("/")), { view: "repositories" });
assert.deepEqual(parseRoute(loc("/invite/abc_123")), { view: "invite", token: "abc_123" });
assert.deepEqual(parseRoute(loc("/attempts/abc")), { view: "repositories" });
for (const route of [{ view: "report", attemptId: 7 }, { view: "ideas", status: "DONE" }, { view: "bottlenecks" }]) {
  assert.deepEqual(parseRoute(loc(routePath(route))), route);
}
console.log("route checks pass");
