import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import LandingPage from "./components/LandingPage";
import RepositoriesPage from "./pages/RepositoriesPage";
import MeetingsPage from "./pages/MeetingsPage";
import IdeasPage from "./pages/IdeasPage";
import BottlenecksPage from "./pages/BottlenecksPage";
import ReportPage from "./pages/ReportPage";
import SettingsPage from "./pages/SettingsPage";
import InvitePage from "./pages/InvitePage";
import LiveAttemptModal from "./components/LiveAttemptModal";
import TourBanner from "./components/TourBanner";
import { TourChecklist, TourOverlay } from "./components/GuidedTour";
import { useGuidedTour } from "./lib/useGuidedTour";
import { Logo } from "./components/Icon";
import { onAuthChanged } from "./lib/firebase";
import { useRoute } from "./lib/route";
import {
  approveIdea,
  deleteIdea,
  deleteMeeting,
  extractIdeas,
  getIdeaCounts,
  health,
  listIdeas,
  listMeetings,
  listRepositories,
  rejectIdea,
  retryIdeaAttempt,
} from "./api";
import "./styles/global.css";

// The tour's last step is done once the bottleneck map has been opened.
const MAP_SEEN_KEY = "tryout.tour.bottlenecks-seen";

const POLL_FIRST_MS = 2500;
const POLL_MAX_MS = 10000;
// A job still "running" after this long is stuck; stop instead of polling forever.
const POLL_GIVE_UP_MS = 20 * 60 * 1000;

function meetingsInFlight(meetings) {
  return meetings.some(
    (meeting) =>
      meeting.status === "PROCESSING" ||
      meeting.status === "PENDING" ||
      meeting.ideas_status === "PROCESSING"
  );
}

function attemptsInFlight(ideas) {
  return ideas.some((idea) =>
    ["QUEUED", "PLANNING", "CODING", "TESTING"].includes(idea.latest_attempt?.status)
  );
}

export default function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [route, navigate] = useRoute();
  const { view, attemptId: reportAttemptId } = route;
  const setView = useCallback((next) => navigate({ view: next }), [navigate]);
  const [liveAttemptId, setLiveAttemptId] = useState(null);
  const [repositories, setRepositories] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [ideas, setIdeas] = useState([]);
  const ideaFilter = route.status || "PENDING";
  const setIdeaFilter = (status) => navigate({ view: "ideas", status });
  const [ideaCounts, setIdeaCounts] = useState({ PENDING: 0, IN_PROCESS: 0, DONE: 0, REJECTED: 0, ALL: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ideasError, setIdeasError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [retryingId, setRetryingId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [online, setOnline] = useState(null);

  // Render nothing until Firebase reports whether a user is restored.
  useEffect(() => {
    const unsubscribe = onAuthChanged((user) => {
      setCurrentUser(user);
      setAuthChecking(false);
    });
    return () => unsubscribe();
  }, []);

  const refresh = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) {
      setLoading(true);
      setError("");
      setIdeasError("");
    }

    const [reposResult, meetingsResult, ideasResult, countsResult] = await Promise.allSettled([
      listRepositories(),
      listMeetings(),
      listIdeas(ideaFilter),
      getIdeaCounts(),
    ]);

    if (reposResult.status === "fulfilled") {
      setRepositories(reposResult.value);
    } else {
      console.error("Failed to load repositories:", reposResult.reason);
      if (!quiet && view === "repositories") {
        setError(
          `Repositories error: ${reposResult.reason?.message || "Failed to load repositories"}`
        );
      }
    }

    let meetingsData = null;
    if (meetingsResult.status === "fulfilled") {
      meetingsData = meetingsResult.value;
      setMeetings(meetingsData);
    } else {
      console.error("Failed to load meetings:", meetingsResult.reason);
      if (!quiet && view === "meetings") {
        setError(
          `Meetings error: ${meetingsResult.reason?.message || "Failed to load meetings"}`
        );
      }
    }

    if (ideasResult.status === "fulfilled") {
      setIdeas(ideasResult.value);
    } else {
      console.error("Failed to load ideas:", ideasResult.reason);
      if (!quiet && view === "ideas") {
        setIdeasError(
          `Ideas error: ${ideasResult.reason?.message || "Failed to load ideas"}`
        );
      }
    }

    if (countsResult.status === "fulfilled") {
      setIdeaCounts(countsResult.value);
    }

    const anySuccess = [reposResult, meetingsResult, ideasResult].some(
      (result) => result.status === "fulfilled"
    );
    if (anySuccess) {
      setOnline(true);
    } else {
      try {
        setOnline(await health());
      } catch {
        setOnline(false);
      }
    }

    if (!quiet) setLoading(false);
    return meetingsData;
  }, [view, ideaFilter]);

  // Load once signed in; before that every API call would just 401.
  useEffect(() => {
    if (!currentUser) return;
    refresh();
    health()
      .then((isUp) => setOnline((prev) => (prev === null ? isUp : prev || isUp)))
      .catch(() => {});
  }, [refresh, currentUser]);

  // Per user: a new evaluator in the same browser starts the tour from step 1.
  const mapSeenKey = `${MAP_SEEN_KEY}:${currentUser?.uid ?? ""}`;
  useEffect(() => {
    if (view === "bottlenecks") localStorage.setItem(mapSeenKey, "1");
  }, [view, mapSeenKey]);
  const mapSeen = view === "bottlenecks" || localStorage.getItem(mapSeenKey) === "1";

  const [catalogOpen, setCatalogOpen] = useState(false);

  // Live evaluator guide: reacts to the workspace's real state.
  const tour = useGuidedTour({
    enabled: Boolean(currentUser?.isEvaluator),
    uid: currentUser?.uid,
    view,
    repositories,
    meetings,
    ideas,
    counts: ideaCounts,
    mapSeen,
    catalogOpen,
  });

  // Poll only what the current page shows, and only while its background work runs.
  // Keyed on booleans so each poll's results don't restart the backoff.
  const meetingsBusy = meetingsInFlight(meetings);
  const attemptsBusy = attemptsInFlight(ideas);
  const reposBusy = repositories.some((repo) => repo.catalog_status === "onboarding");
  useEffect(() => {
    const watchMeetings = (view === "meetings" || view === "ideas") && meetingsBusy;
    // Extraction finishing on the ideas page adds new ideas, so watch those too.
    const watchIdeas = view === "ideas" && (attemptsBusy || meetingsBusy);
    // The Repositories page polls its own cards; elsewhere an analysis would never finish on screen.
    const watchRepos = view !== "repositories" && reposBusy;
    if (!watchMeetings && !watchIdeas && !watchRepos) return undefined;

    const startedAt = Date.now();
    let delay = POLL_FIRST_MS;
    let timer = null;
    let cancelled = false;
    let running = false;

    async function tick() {
      running = true;
      if (!document.hidden) {
        const [nextMeetings, nextIdeas, nextCounts, nextRepos] = await Promise.all([
          watchMeetings ? listMeetings().catch(() => null) : null,
          watchIdeas ? listIdeas(ideaFilter).catch(() => null) : null,
          watchIdeas ? getIdeaCounts().catch(() => null) : null,
          watchRepos ? listRepositories().catch(() => null) : null,
        ]);
        if (cancelled) return;
        if (nextRepos) setRepositories(nextRepos);
        if (nextMeetings) setMeetings(nextMeetings);
        if (nextIdeas) setIdeas(nextIdeas);
        if (nextCounts) setIdeaCounts(nextCounts);
        delay = Math.min(delay * 1.5, POLL_MAX_MS);
      }
      running = false;
      if (!cancelled && Date.now() - startedAt < POLL_GIVE_UP_MS) {
        timer = setTimeout(tick, delay);
      }
    }

    // Catch up as soon as a hidden tab comes back instead of waiting out the delay.
    function onVisible() {
      if (document.hidden || cancelled || running) return;
      clearTimeout(timer);
      delay = POLL_FIRST_MS;
      tick();
    }

    timer = setTimeout(tick, delay);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [view, meetingsBusy, attemptsBusy, reposBusy, ideaFilter]);

  function handleUploaded(result) {
    setMeetings((current) => {
      const next = current.filter((meeting) => meeting.id !== result.meeting.id);
      return [result.meeting, ...next];
    });
    setView("meetings");
  }

  function handleRepoOnboarded(newRepo) {
    setRepositories((current) => {
      const filtered = current.filter((r) => r.id !== newRepo.id);
      return [newRepo, ...filtered];
    });
  }

  function handleRepoDeleted(repoId) {
    setRepositories((current) => current.filter((r) => r.id !== repoId));
  }

  async function handleRetryIdeas(meetingId) {
    setRetryingId(meetingId);
    setError("");
    try {
      const result = await extractIdeas(meetingId);
      setMeetings((current) =>
        current.map((meeting) =>
          meeting.id === result.meeting.id ? { ...meeting, ...result.meeting } : meeting
        )
      );
    } catch (problem) {
      setError(problem.message);
      if (problem.payload?.meeting) {
        setMeetings((current) =>
          current.map((meeting) =>
            meeting.id === problem.payload.meeting.id
              ? { ...meeting, ...problem.payload.meeting }
              : meeting
          )
        );
      }
    } finally {
      setRetryingId(null);
    }
  }

  async function handleIdeaFilterChange(newFilter) {
    setIdeaFilter(newFilter);
    setLoading(true);
    setIdeasError("");
    try {
      const [filteredIdeas, counts] = await Promise.all([
        listIdeas(newFilter),
        getIdeaCounts().catch(() => null),
      ]);
      setIdeas(filteredIdeas);
      if (counts) setIdeaCounts(counts);
    } catch (err) {
      setIdeasError(err.message || "Failed to load ideas");
    } finally {
      setLoading(false);
    }
  }

  const openReport = useCallback((attemptId) => {
    setLiveAttemptId(null);
    navigate({ view: "report", attemptId });
  }, [navigate]);

  async function handleApprove(ideaId, repositoryId) {
    setBusyId(ideaId);
    setIdeasError("");
    try {
      const updated = await approveIdea(ideaId, repositoryId);
      setLiveAttemptId(updated.latest_attempt?.id ?? null);
      setIdeas((current) =>
        ideaFilter === "PENDING"
          ? current.filter((idea) => idea.id !== updated.id)
          : current.map((idea) => (idea.id === updated.id ? { ...idea, ...updated } : idea))
      );
      setIdeaFilter("IN_PROCESS");
      getIdeaCounts().then(setIdeaCounts).catch(() => {});
    } catch (problem) {
      setIdeasError(problem.message);
    } finally {
      setBusyId(null);
    }
  }

  async function handleRetryAttempt(ideaId) {
    setBusyId(ideaId);
    setIdeasError("");
    try {
      const updated = await retryIdeaAttempt(ideaId);
      setLiveAttemptId(updated.latest_attempt?.id ?? null);
      setIdeas((current) =>
        current.map((idea) => (idea.id === updated.id ? { ...idea, ...updated } : idea))
      );
    } catch (problem) {
      setIdeasError(problem.message);
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(ideaId) {
    setBusyId(ideaId);
    setIdeasError("");
    try {
      const updated = await rejectIdea(ideaId);
      setIdeas((current) =>
        ideaFilter === "PENDING"
          ? current.filter((idea) => idea.id !== updated.id)
          : current.map((idea) => (idea.id === updated.id ? { ...idea, ...updated } : idea))
      );
      getIdeaCounts().then(setIdeaCounts).catch(() => {});
    } catch (problem) {
      setIdeasError(problem.message);
    } finally {
      setBusyId(null);
    }
  }

  async function handleDeleteMeeting(meetingId) {
    if (!window.confirm("Delete this meeting and its ideas?")) return;
    setDeletingId(`meeting-${meetingId}`);
    setError("");
    try {
      await deleteMeeting(meetingId);
      setMeetings((current) => current.filter((meeting) => meeting.id !== meetingId));
      setIdeas((current) => current.filter((idea) => idea.meeting_id !== meetingId));
      getIdeaCounts().then(setIdeaCounts).catch(() => {});
    } catch (problem) {
      setError(problem.message);
    } finally {
      setDeletingId(null);
    }
  }

  async function handleDeleteIdea(ideaId) {
    if (!window.confirm("Delete this idea?")) return;
    setDeletingId(`idea-${ideaId}`);
    setIdeasError("");
    try {
      await deleteIdea(ideaId);
      setIdeas((current) => current.filter((idea) => idea.id !== ideaId));
      getIdeaCounts().then(setIdeaCounts).catch(() => {});
    } catch (problem) {
      setIdeasError(problem.message);
    } finally {
      setDeletingId(null);
    }
  }

  if (authChecking) {
    return (
      <div className="boot-screen" role="status">
        <Logo size={36} />
        <span className="spinner spinner-muted" />
        <span className="sr-only">Loading workspace…</span>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <LandingPage
        onLoginSuccess={(user) => {
          setCurrentUser(user);
          // A fresh evaluator starts the tour at step 1, not wherever the last one left off.
          if (user?.isEvaluator) navigate({ view: "repositories" });
        }}
      />
    );
  }

  return (
    <div className="shell">
      <Sidebar
        view={view}
        onNavigate={setView}
        counts={{
          repositories: repositories.length,
          meetings: meetings.length,
          ideas: ideaCounts.PENDING,
        }}
        online={online}
        user={currentUser}
        onLogout={() => setCurrentUser(null)}
        tourSlot={<TourChecklist tour={tour} />}
      />

      <main className="main">
        <div className="main-inner">
        <TourBanner
          view={view}
          onNavigate={setView}
          done={[
            repositories.length > 0,
            meetings.length > 0,
            ideaCounts.IN_PROCESS + ideaCounts.DONE > 0,
            ideaCounts.DONE > 0,
            mapSeen,
          ]}
        />
        {view === "repositories" ? (
          <RepositoriesPage
            repositories={repositories}
            loading={loading}
            error={error}
            onOnboarded={handleRepoOnboarded}
            onDeleted={handleRepoDeleted}
            isEvaluator={Boolean(currentUser?.isEvaluator)}
            onCatalogOpenChange={setCatalogOpen}
          />
        ) : view === "meetings" ? (
          <MeetingsPage
            meetings={meetings}
            loading={loading}
            error={error}
            retryingId={retryingId}
            deletingId={
              deletingId?.startsWith("meeting-")
                ? Number(deletingId.slice("meeting-".length))
                : null
            }
            onUploaded={handleUploaded}
            onRetryIdeas={handleRetryIdeas}
            onDelete={handleDeleteMeeting}
          />
        ) : view === "bottlenecks" ? (
          <BottlenecksPage />
        ) : view === "invite" ? (
          <InvitePage token={route.token} />
        ) : view === "settings" ? (
          <SettingsPage />
        ) : view === "report" ? (
          <ReportPage attemptId={reportAttemptId} onBack={() => setView("ideas")} />
        ) : (
          <IdeasPage
            ideas={ideas}
            repositories={repositories}
            counts={ideaCounts}
            filter={ideaFilter}
            onFilterChange={handleIdeaFilterChange}
            loading={loading}
            error={ideasError || error}
            busyId={busyId}
            deletingId={
              deletingId?.startsWith("idea-")
                ? Number(deletingId.slice("idea-".length))
                : null
            }
            onApprove={handleApprove}
            onRetryAttempt={handleRetryAttempt}
            onOpenReport={openReport}
            onWatchLive={setLiveAttemptId}
            onReject={handleReject}
            onDelete={handleDeleteIdea}
          />
        )}
        </div>
      </main>
      <TourOverlay tour={tour} suspended={Boolean(liveAttemptId)} />
      {liveAttemptId && (
        <LiveAttemptModal
          attemptId={liveAttemptId}
          onClose={() => setLiveAttemptId(null)}
          onDone={openReport}
        />
      )}
    </div>
  );
}
