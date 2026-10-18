// Live evaluator guide: works out, from the workspace's real state, the one thing
// to show the evaluator next. Nothing here is scripted by time or by a fixed step
// counter, so refreshing, skipping around or finishing a job elsewhere always
// lands on the right bubble.

export const STAGE_NAMES = [
  "Onboard repo",
  "Ingest meeting",
  "Approve idea",
  "Run tryout",
  "Bottleneck map",
];

export const CHECKLIST = [
  "Connect the demo repository",
  "Load the demo meeting",
  "Approve an idea",
  "Review the attempt",
  "Open the bottleneck map",
];

const RUNNING = ["QUEUED", "PLANNING", "CODING", "TESTING"];

export function meetingsBusy(meetings = []) {
  return meetings.some(
    (meeting) =>
      meeting.status === "PROCESSING" ||
      meeting.status === "PENDING" ||
      meeting.ideas_status === "PROCESSING"
  );
}

const nav = (id) => `[data-tour="nav-${id}"]`;
const filter = (id) => `[data-tour="filter-${id}"]`;
const t = (sel, extra = {}) => ({ sel, ...extra });

export function deriveTour({
  view,
  repositories = [],
  meetings = [],
  ideas = [],
  counts = {},
  reportSeen = false,
  mapSeen = false,
  finished = false,
}) {
  const repoReady = repositories.some((r) => r.catalog_status === "ready");
  const repoBusy = repositories.some((r) => r.catalog_status === "onboarding");
  const repoFailed = repositories.some((r) => r.catalog_status === "failed");
  const hasMeeting = meetings.length > 0;
  const meetingBusy = meetingsBusy(meetings);
  const pending = (counts.PENDING ?? 0) > 0;
  // A report only exists for a finished attempt; counts catch up a moment later.
  const onReport = view === "report";
  const approved = onReport || (counts.IN_PROCESS ?? 0) + (counts.DONE ?? 0) > 0;
  const done = onReport || (counts.DONE ?? 0) > 0;
  const attemptRunning = ideas.some((i) => RUNNING.includes(i.latest_attempt?.status));
  const attemptFailed = ideas.some(
    (i) =>
      ["FAILED", "READY_FOR_REVIEW"].includes(i.latest_attempt?.status) &&
      !i.latest_attempt?.pull_request_url
  );

  const flags = [repoReady, hasMeeting, approved, reportSeen, mapSeen];
  const first = flags.indexOf(false);
  const stage = first === -1 ? 5 : first;

  let step = null;

  if (!repoReady) {
    if (repoBusy) {
      step = {
        id: "repo-wait", kind: "wait", stage: 0,
        title: "Mapping the codebase…",
        body: "tryout is reading acme-store and building a catalog of its modules, routes and owners. The next step appears when it is ready.",
        wait: "Analyzing in the background",
        note: "Usually about 30 seconds. You can look around.",
        targets: [t('[data-tour="repo-card"]'), t(nav("repositories"))],
      };
    } else if (repoFailed) {
      step = {
        id: "repo-failed", kind: "do", stage: 0,
        title: "The analysis failed",
        body: "Nothing is lost. Run it again.",
        hint: "Click Retry analysis",
        targets: [t('[data-tour="repo-retry"]'), t('[data-tour="repo-card"]')],
      };
    } else if (view !== "repositories") {
      step = {
        id: "repo-nav", kind: "do", stage: 0,
        title: "Start with a repository",
        body: "tryout grounds every idea in a real codebase, so we begin there.",
        hint: "Open Repositories",
        targets: [t(nav("repositories"))],
      };
    } else {
      step = {
        id: "repo-connect", kind: "do", stage: 0,
        title: "Start with the demo repository",
        body: "No GitHub access needed. Acme Store is a small Flask app prepared for evaluators.",
        hint: "Click Demo repository",
        targets: [
          t('[data-tour="demo-connect"]', {
            title: "Connect it",
            body: "tryout reads the code and maps its modules, routes, models and owners into a catalog.",
            hint: "Click Connect demo repository",
          }),
          t('[data-tour="demo-tab"]'),
        ],
      };
    }
  } else if (!hasMeeting) {
    step = view !== "meetings"
      ? {
          id: "meet-nav", kind: "do", stage: 1,
          title: "Catalog ready",
          body: "acme-store is mapped. Every idea will be checked against it. Now give tryout a meeting to listen to.",
          hint: "Open Meetings",
          targets: [t(nav("meetings"))],
        }
      : {
          id: "meet-load", kind: "do", stage: 1,
          title: "Give it a meeting",
          body: "Load a sample weekly ops sync. No file needed.",
          hint: "Click Load demo transcript",
          targets: [t('[data-tour="load-demo"]')],
        };
  } else if (meetingBusy) {
    step = {
      id: "meet-wait", kind: "wait", stage: 1,
      title: "Reading the meeting…",
      body: "tryout writes the minutes, then pulls out ideas that fit the acme-store catalog.",
      wait: "Writing minutes and extracting ideas",
      note: "Usually under a minute. The next step appears when it is done.",
      targets: view === "meetings"
        ? [t('[data-tour="meeting-list"]'), t(nav("meetings"))]
        : [t(nav("meetings"))],
    };
  } else if (!approved) {
    // Idea counts are only refreshed on the Ideas page, so off it we trust the finished meeting.
    if (pending || view !== "ideas") {
      step = view !== "ideas"
        ? {
            id: "idea-nav", kind: "do", stage: 2,
            title: "An idea is waiting for you",
            body: "The meeting is processed and tryout found an idea that fits the codebase.",
            hint: "Open Ideas",
            targets: [t(nav("ideas"))],
          }
        : {
            id: "idea-approve", kind: "do", stage: 2,
            title: "Open the idea",
            body: "Read what tryout wants to build and the line from the meeting it came from.",
            hint: "Click the idea",
            targets: [
              t('[data-tour="approve"]', {
                title: "You are the gate",
                body: "Nothing is built until a person approves. Approve it and tryout writes the change and runs the tests.",
                hint: "Click Approve",
              }),
              t('.idea-row[data-idea-status="PENDING"] .row-header'),
              t(filter("PENDING")),
            ],
          };
    }
  } else if (!done) {
    if (attemptRunning) {
      step = {
        id: "attempt-wait", kind: "wait", stage: 3,
        title: "tryout is attempting it…",
        body: "It writes the change, mocks what it cannot reach and runs the tests. The demo repository is missing a notifications permission on purpose, so expect a blocker.",
        wait: "Working in the background",
        note: "A few minutes. The next step appears when it finishes.",
        targets: view === "ideas"
          ? [t('.idea-row[data-attempt-running="true"]'), t(filter("IN_PROCESS"))]
          : [t(nav("ideas"))],
      };
    } else if (attemptFailed) {
      step = {
        id: "attempt-failed", kind: "do", stage: 3,
        title: "The attempt did not finish",
        body: "Open the idea and retry it.",
        hint: "Click Retry attempt",
        targets: view === "ideas"
          ? [
              t('[data-tour="retry-attempt"]'),
              t('.idea-row[data-attempt-failed="true"] .row-header', { hint: "Open the idea, then click Retry attempt" }),
              t(filter("IN_PROCESS"), { hint: "Click In process" }),
            ]
          : [t(nav("ideas"))],
      };
    } else {
      step = {
        id: "attempt-find", kind: "do", stage: 3,
        title: "Follow the attempt",
        body: "Your approved idea is under In process.",
        hint: view === "ideas" ? "Click In process" : "Open Ideas",
        targets: view === "ideas" ? [t(filter("IN_PROCESS"))] : [t(nav("ideas"))],
      };
    }
  } else if (!reportSeen) {
    if (view === "report") {
      step = {
        id: "report", kind: "info", stage: 3,
        title: "Review what it did",
        body: "The pull request link is up here. Below, Production readiness lists each blocker the agent hit and which team owns it.",
        next: "Next",
        targets: [t('[data-tour="report-summary"]')],
      };
    } else {
      step = {
        id: "report-open", kind: "do", stage: 3,
        title: "Attempt finished",
        body: "It hit a real blocker before anyone spent engineering time on it.",
        hint: view === "ideas" ? "Click View report" : "Open Ideas",
        targets: view === "ideas"
          ? [
              t('[data-tour="view-report"]'),
              t('.idea-row[data-attempt-status="COMPLETE"] .row-header', { hint: "Open the idea, then click View report" }),
              t(filter("DONE"), { hint: "Click Done" }),
            ]
          : [t(nav("ideas"))],
      };
    }
  } else if (view !== "bottlenecks" && !mapSeen) {
    step = {
      id: "map-nav", kind: "do", stage: 4,
      title: "Zoom out",
      body: "Blockers from every attempt add up into one map.",
      hint: "Open Bottleneck map",
      targets: [t(nav("bottlenecks"))],
    };
  } else if (view === "bottlenecks" && !finished) {
    step = {
      id: "map", kind: "info", stage: 4,
      title: "Fix the bottleneck, not the ticket",
      body: "Blockers are grouped by category, dependency and team, so you can see which services and teams other work waits on.",
      next: "Finish",
      targets: [t('[data-tour="bottleneck-stats"]')],
    };
  }

  return { stage, flags, step };
}
