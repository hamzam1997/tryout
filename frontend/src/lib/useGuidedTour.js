import { useCallback, useEffect, useMemo, useState } from "react";
import { deriveTour } from "./tour";

function readFlag(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function writeFlag(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Private mode: the guide still works for this page load.
  }
}

export function useGuidedTour({ enabled, uid, view, repositories, meetings, ideas, counts, mapSeen }) {
  const key = (name) => `tryout.tour.${name}:${uid ?? ""}`;
  const [mode, setModeState] = useState(() => readFlag(key("mode"))); // null | guided | paused | done
  const [reportSeen, setReportSeen] = useState(() => readFlag(key("report-seen")) === "1");
  const [finished, setFinished] = useState(() => readFlag(key("finished")) === "1");

  // A different evaluator in the same browser has their own progress.
  const [loadedFor, setLoadedFor] = useState(uid);
  if (loadedFor !== uid) {
    setLoadedFor(uid);
    setModeState(readFlag(key("mode")));
    setReportSeen(readFlag(key("report-seen")) === "1");
    setFinished(readFlag(key("finished")) === "1");
  }

  const setMode = useCallback((next) => {
    writeFlag(key("mode"), next);
    setModeState(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uid]);

  const markReportSeen = useCallback(() => {
    writeFlag(key("report-seen"), "1");
    setReportSeen(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uid]);

  // Leaving the report counts as having reviewed it.
  useEffect(() => {
    if (!enabled || view !== "report") return undefined;
    return () => markReportSeen();
  }, [enabled, view, markReportSeen]);

  const finish = useCallback(() => {
    writeFlag(key("finished"), "1");
    writeFlag(key("mode"), "done");
    setFinished(true);
    setModeState("done");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uid]);

  const derived = useMemo(
    () => deriveTour({ view, repositories, meetings, ideas, counts, reportSeen, mapSeen, finished }),
    [view, repositories, meetings, ideas, counts, reportSeen, mapSeen, finished]
  );

  return { enabled, mode, setMode, markReportSeen, finish, ...derived };
}

