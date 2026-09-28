import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import MeetingsPage from "./pages/MeetingsPage";
import IdeasPage from "./pages/IdeasPage";
import { approveIdea, health, listIdeas, listMeetings, rejectIdea } from "./api";
import "./styles/global.css";

export default function App() {
  const [view, setView] = useState("meetings");
  const [meetings, setMeetings] = useState([]);
  const [ideas, setIdeas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ideasError, setIdeasError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [online, setOnline] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    setIdeasError("");
    try {
      const [nextMeetings, nextIdeas] = await Promise.all([listMeetings(), listIdeas()]);
      setMeetings(nextMeetings);
      setIdeas(nextIdeas);
      setOnline(true);
    } catch (problem) {
      setError(problem.message);
      setOnline(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    health().then(setOnline).catch(() => setOnline(false));
  }, [refresh]);

  function handleUploaded(result) {
    setMeetings((current) => [result.meeting, ...current]);
    if (Array.isArray(result.ideas) && result.ideas.length > 0) {
      setIdeas((current) => {
        const existingIds = new Set(current.map((idea) => idea.id));
        const fresh = result.ideas.filter((idea) => !existingIds.has(idea.id));
        return [...fresh, ...current];
      });
      setView("ideas");
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
        counts={{ meetings: meetings.length, ideas: pendingIdeas }}
        online={online}
      />

      <main className="main">
        {view === "meetings" ? (
          <MeetingsPage
            meetings={meetings}
            loading={loading}
            error={error}
            onUploaded={handleUploaded}
            onRefresh={refresh}
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
