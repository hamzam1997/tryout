import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import RepositoriesPage from "./pages/RepositoriesPage";
import MeetingsPage from "./pages/MeetingsPage";
import IdeasPage from "./pages/IdeasPage";
import { health, listMeetings, listRepositories } from "./api";
import "./styles/global.css";

export default function App() {
  const [view, setView] = useState("repositories");
  const [repositories, setRepositories] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [online, setOnline] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [reposData, meetingsData] = await Promise.all([
        listRepositories(),
        listMeetings(),
      ]);
      setRepositories(reposData);
      setMeetings(meetingsData);
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
  }

  function handleRepoOnboarded(newRepo) {
    setRepositories((current) => {
      const filtered = current.filter((r) => r.id !== newRepo.id);
      return [newRepo, ...filtered];
    });
  }

  return (
    <div className="shell">
      <Sidebar
        view={view}
        onNavigate={setView}
        counts={{
          repositories: repositories.length,
          meetings: meetings.length,
          ideas: 0,
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
            onUploaded={handleUploaded}
            onRefresh={refresh}
          />
        ) : (
          <IdeasPage />
        )}
      </main>
    </div>
  );
}
