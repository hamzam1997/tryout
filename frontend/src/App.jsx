import { useCallback, useEffect, useRef, useState } from "react";
import Sidebar from "./components/Sidebar";
import RepositoriesPage from "./pages/RepositoriesPage";
import MeetingsPage from "./pages/MeetingsPage";
import IdeasPage from "./pages/IdeasPage";
import {
  approveIdea,
  extractIdeas,
  health,
  listIdeas,
  listMeetings,
  listRepositories,
  rejectIdea,
} from "./api";
import "./styles/global.css";

const IDEAS_POLL_MS = 2500;

function ideasStillRunning(meetings) {
  return meetings.some((meeting) => meeting.ideas_status === "PROCESSING");
}

export default function App() {
  const [view, setView] = useState("repositories");
  const [repositories, setRepositories] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [ideas, setIdeas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ideasError, setIdeasError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [retryingId, setRetryingId] = useState(null);
  const [online, setOnline] = useState(null);
  const pollRef = useRef(null);

  const refresh = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) {
      setLoading(true);
      setError("");
      setIdeasError("");
    }

    const [reposResult, meetingsResult, ideasResult] = await Promise.allSettled([
      listRepositories(),
      listMeetings(),
      listIdeas(),
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
  }, [view]);

  useEffect(() => {
    refresh();
    health()
      .then((isUp) => setOnline((prev) => (prev === null ? isUp : prev || isUp)))
      .catch(() => {});
  }, [refresh]);

  // Poll while any meeting has background idea extraction in flight.
  useEffect(() => {
    if (!ideasStillRunning(meetings)) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return undefined;
    }

    if (pollRef.current) return undefined;

    pollRef.current = setInterval(async () => {
      const nextMeetings = await refresh({ quiet: true });
      if (nextMeetings && !ideasStillRunning(nextMeetings)) {
        const nextIdeas = await listIdeas().catch(() => null);
        if (nextIdeas) setIdeas(nextIdeas);
      }
    }, IDEAS_POLL_MS);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [meetings, refresh]);

  function handleUploaded(result) {
    setMeetings((current) => [result.meeting, ...current]);
    setView("meetings");
  }

  function handleRepoOnboarded(newRepo) {
    setRepositories((current) => {
      const filtered = current.filter((r) => r.id !== newRepo.id);
      return [newRepo, ...filtered];
    });
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

  async function handleApprove(ideaId) {
    setBusyId(ideaId);
    setIdeasError("");
    try {
      const updated = await approveIdea(ideaId);
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
        current.map((idea) => (idea.id === updated.id ? { ...idea, ...updated } : idea))
      );
    } catch (problem) {
      setIdeasError(problem.message);
    } finally {
      setBusyId(null);
    }
  }

  const pendingIdeas = ideas.filter((idea) => idea.status === "PENDING").length;

  return (
    <div className="shell">
      <Sidebar
        view={view}
        onNavigate={setView}
        counts={{
          repositories: repositories.length,
          meetings: meetings.length,
          ideas: pendingIdeas,
        }}
        online={online}
      />

      <main className="main">
        {view === "repositories" ? (
          <RepositoriesPage
            repositories={repositories}
            loading={loading}
            error={error}
            onRefresh={refresh}
            onOnboarded={handleRepoOnboarded}
          />
        ) : view === "meetings" ? (
          <MeetingsPage
            meetings={meetings}
            loading={loading}
            error={error}
            retryingId={retryingId}
            onUploaded={handleUploaded}
            onRefresh={refresh}
            onRetryIdeas={handleRetryIdeas}
          />
        ) : (
          <IdeasPage
            ideas={ideas}
            loading={loading}
            error={ideasError || error}
            busyId={busyId}
            onApprove={handleApprove}
            onReject={handleReject}
            onRefresh={refresh}
          />
        )}
      </main>
    </div>
  );
}
