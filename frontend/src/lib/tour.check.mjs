import assert from "node:assert/strict";
import { deriveTour } from "./tour.js";

const repo = (catalog_status) => ({ id: 1, catalog_status });
const meeting = (over = {}) => ({ id: 1, status: "COMPLETE", ideas_status: "COMPLETE", ...over });
const counts = (over = {}) => ({ PENDING: 0, IN_PROCESS: 0, DONE: 0, ...over });
const id = (state) => deriveTour(state).step?.id;

assert.equal(id({ view: "meetings" }), "repo-nav");
assert.equal(id({ view: "repositories" }), "repo-connect");
assert.equal(id({ view: "repositories", repositories: [repo("onboarding")] }), "repo-wait");
assert.equal(id({ view: "repositories", repositories: [repo("failed")] }), "repo-failed");
assert.equal(id({ view: "repositories", repositories: [repo("ready")] }), "meet-nav");
assert.equal(id({ view: "meetings", repositories: [repo("ready")] }), "meet-load");
assert.equal(
  id({ view: "meetings", repositories: [repo("ready")], meetings: [meeting({ status: "PROCESSING" })] }),
  "meet-wait"
);
const withMeeting = { repositories: [repo("ready")], meetings: [meeting()] };
assert.equal(id({ ...withMeeting, view: "meetings", counts: counts({ PENDING: 1 }) }), "idea-nav");
assert.equal(id({ ...withMeeting, view: "meetings", counts: counts() }), "idea-nav", "stale counts off the Ideas page");
assert.equal(id({ ...withMeeting, view: "ideas", counts: counts({ PENDING: 1 }) }), "idea-approve");
assert.equal(id({ ...withMeeting, view: "ideas", counts: counts() }), undefined);
const running = [{ latest_attempt: { status: "CODING" } }];
assert.equal(id({ ...withMeeting, view: "ideas", counts: counts({ IN_PROCESS: 1 }), ideas: running }), "attempt-wait");
assert.equal(
  id({ ...withMeeting, view: "ideas", counts: counts({ IN_PROCESS: 1 }), ideas: [{ latest_attempt: { status: "FAILED" } }] }),
  "attempt-failed"
);
const finished = { ...withMeeting, counts: counts({ DONE: 1 }) };
assert.equal(id({ ...finished, view: "ideas" }), "report-open");
assert.equal(id({ ...finished, view: "report" }), "report");
assert.equal(id({ ...withMeeting, view: "report", counts: counts({ IN_PROCESS: 1 }) }), "report", "report before counts refresh");
assert.equal(id({ ...finished, view: "ideas", reportSeen: true }), "map-nav");
assert.equal(id({ ...finished, view: "bottlenecks", reportSeen: true, mapSeen: true }), "map");
assert.equal(id({ ...finished, view: "bottlenecks", reportSeen: true, mapSeen: true, finished: true }), undefined);
assert.equal(deriveTour({ ...finished, view: "ideas", reportSeen: true, mapSeen: true, finished: true }).stage, 5);
console.log("tour.check ok");
