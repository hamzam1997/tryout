import { useCallback, useEffect, useRef, useState } from "react";
import Sidebar from "./components/Sidebar";
import LandingPage from "./components/LandingPage";
import RepositoriesPage from "./pages/RepositoriesPage";
import MeetingsPage from "./pages/MeetingsPage";
import IdeasPage from "./pages/IdeasPage";
import { onAuthChanged, checkSessionExpired } from "./lib/firebase";
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
} from "./api";
import "./styles/global.css";

const PIPELINE_POLL_MS = 2500;

function pipelineStillRunning(meetings) {
  return meetings.some(
    (meeting) =>
      meeting.status === "PROCESSING" ||
      meeting.status === "PENDING" ||
      meeting.ideas_status === "PROCESSING"
  );
}

export default function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [view, setView] = useState("repositories");
  const [repositories, setRepositories] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [ideas, setIdeas] = useState([]);
  const [ideaFilter, setIdeaFilter] = useState("PENDING");
  const [ideaCounts, setIdeaCounts] = useState({ PENDING: 0, IN_PROCESS: 0, REJECTED: 0, ALL: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ideasError, setIdeasError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [retryingId, setRetryingId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [online, setOnline] = useState(null);
  const pollRef = useRef(null);

  // Monitor auth state changes and session expiration
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

  useEffect(() => {
    refresh();
    health()
      .then((isUp) => setOnline((prev) => (prev === null ? isUp : prev || isUp)))
      .catch(() => {});
  }, [refresh]);

  // Poll while minutes or idea extraction is running in the background.
  useEffect(() => {
    if (!pipelineStillRunning(meetings)) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return undefined;
    }

    if (pollRef.current) return undefined;

    pollRef.current = setInterval(async () => {
      const nextMeetings = await refresh({ quiet: true });
      if (nextMeetings && !pipelineStillRunning(nextMeetings)) {
        const [nextIdeas, nextCounts] = await Promise.all([
          listIdeas(ideaFilter).catch(() => null),
          getIdeaCounts().catch(() => null),
        ]);
        if (nextIdeas) setIdeas(nextIdeas);
        if (nextCounts) setIdeaCounts(nextCounts);
      }
    }, PIPELINE_POLL_MS);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [meetings, refresh, ideaFilter]);

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

  async function handleApprove(ideaId, approvedBy) {
    setBusyId(ideaId);
    setIdeasError("");
    try {
      const updated = await approveIdea(ideaId, approvedBy);
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
      <div className="landing-wrap">
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "16px", color: "var(--on-surface-variant)" }}>
          <div className="spinner" style={{ width: "32px", height: "32px", borderWidth: "3px" }} />
          <span>Loading workspace...</span>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return <LandingPage onLoginSuccess={(user) => { setCurrentUser(user); refresh(); }} />;
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
      />

      <main className="main">
        {view === "repositories" ? (
          <RepositoriesPage
            repositories={repositories}
            loading={loading}
            error={error}
            onOnboarded={handleRepoOnboarded}
            onDeleted={handleRepoDeleted}
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
        ) : (
          <IdeasPage
            ideas={ideas}
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
            onReject={handleReject}
            onDelete={handleDeleteIdea}
          />
        )}
      </main>
    </div>
  );
}
