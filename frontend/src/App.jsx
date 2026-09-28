import { useCallback, useEffect, useState } from "react";
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

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    setIdeasError("");

    const [reposResult, meetingsResult, ideasResult] = await Promise.allSettled([
      listRepositories(),
      listMeetings(),
      listIdeas(),
    ]);

    if (reposResult.status === "fulfilled") {
      setRepositories(reposResult.value);
    } else {
      console.error("Failed to load repositories:", reposResult.reason);
      if (view === "repositories") {
        setError(`Repositories error: ${reposResult.reason?.message || "Failed to load repositories"}`);
      }
    }

    if (meetingsResult.status === "fulfilled") {
      setMeetings(meetingsResult.value);
    } else {
      console.error("Failed to load meetings:", meetingsResult.reason);
      if (view === "meetings") {
        setError(`Meetings error: ${meetingsResult.reason?.message || "Failed to load meetings"}`);
      }
    }

    if (ideasResult.status === "fulfilled") {
      setIdeas(ideasResult.value);
    } else {
      console.error("Failed to load ideas:", ideasResult.reason);
      if (view === "ideas") {
        setIdeasError(`Ideas error: ${ideasResult.reason?.message || "Failed to load ideas"}`);
      }
    }

    const anySuccess = [reposResult, meetingsResult, ideasResult].some((r) => r.status === "fulfilled");
    if (anySuccess) {
      setOnline(true);
    } else {
      try {
        const isHealthy = await health();
        setOnline(isHealthy);
      } catch {
        setOnline(false);
      }
    }

    setLoading(false);
  }, [view]);

  useEffect(() => {
    refresh();
    health().then((isUp) => setOnline((prev) => (prev === null ? isUp : prev || isUp))).catch(() => {});
  }, [refresh]);

  function mergeIdeas(incoming) {
    if (!Array.isArray(incoming) || incoming.length === 0) return;
    setIdeas((current) => {
      const existingIds = new Set(current.map((idea) => idea.id));
      const fresh = incoming.filter((idea) => !existingIds.has(idea.id));
      return [...fresh, ...current];
    });
  }

  function handleUploaded(result) {
    setMeetings((current) => [result.meeting, ...current]);
    mergeIdeas(result.ideas);
    if (result.ideas_error || result.meeting?.ideas_error) {
      setView("meetings");
      return;
    }
    if (Array.isArray(result.ideas) && result.ideas.length > 0) {
      setView("ideas");
    }
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
      mergeIdeas(result.ideas);
      if (Array.isArray(result.ideas) && result.ideas.length > 0) {
        setView("ideas");
      }
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
      } else {
        try {
          setMeetings(await listMeetings());
        } catch {
          /* keep existing list */
        }
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
