import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import MeetingsPage from "./pages/MeetingsPage";
import IdeasPage from "./pages/IdeasPage";
import { health, listMeetings } from "./api";
import "./styles/global.css";

export default function App() {
  const [view, setView] = useState("meetings");
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [online, setOnline] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setMeetings(await listMeetings());
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
    // The response carries the finished meeting, so show it without a round trip.
    setMeetings((current) => [result.meeting, ...current]);
  }

  return (
    <div className="shell">
      <Sidebar
        view={view}
        onNavigate={setView}
        counts={{ meetings: meetings.length, ideas: 0 }}
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
          <IdeasPage />
        )}
      </main>
    </div>
  );
}
