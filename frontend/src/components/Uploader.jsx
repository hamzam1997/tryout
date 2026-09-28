import { useRef, useState } from "react";
import { loadDemoMeeting, uploadTranscript } from "../api";

const ACCEPTED = [".vtt", ".srt", ".txt"];
const MAX_BYTES = 2 * 1024 * 1024;

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function extensionOf(name) {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot).toLowerCase();
}

export default function Uploader({ onUploaded }) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [occurredAt, setOccurredAt] = useState("");
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function accept(candidate) {
    setError("");
    if (!candidate) return;

    if (!ACCEPTED.includes(extensionOf(candidate.name))) {
      setError(`Unsupported file type. Expected ${ACCEPTED.join(", ")}.`);
      return;
    }
    if (candidate.size > MAX_BYTES) {
      setError("That file is over the 2MB limit.");
      return;
    }
    setFile(candidate);
  }

  function clear() {
    setFile(null);
    setError("");
    if (inputRef.current) inputRef.current.value = "";
  }

  function onDrop(event) {
    event.preventDefault();
    setDragging(false);
    accept(event.dataTransfer.files?.[0]);
  }

  async function onSubmit(event) {
    event.preventDefault();
    if (!file || busy) return;

    setBusy(true);
    setError("");
    try {
      const result = await uploadTranscript({ file, title, occurredAt });
      clear();
      setTitle("");
      setOccurredAt("");
      onUploaded(result);
    } catch (problem) {
      setError(problem.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleLoadDemo() {
    setBusy(true);
    setError("");
    try {
      const result = await loadDemoMeeting();
      clear();
      onUploaded(result);
    } catch (problem) {
      setError(problem.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h2>Upload a transcript</h2>
          <span className="card-hint">{ACCEPTED.join(", ")} · max 2MB</span>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={handleLoadDemo}
          disabled={busy}
        >
          {busy ? "Loading…" : "Load Demo Transcript (Acme Store)"}
        </button>
      </div>

      <div className="card-body">
        <form onSubmit={onSubmit}>
          {file ? (
            <div className="file">
              <span className="file-icon">{extensionOf(file.name).slice(1)}</span>
              <div className="file-meta">
                <div className="file-name">{file.name}</div>
                <div className="file-size">{formatSize(file.size)}</div>
              </div>
              <button type="button" className="file-x" onClick={clear} aria-label="Remove file">
                &times;
              </button>
            </div>
          ) : (
            <label
              className={`drop${dragging ? " is-over" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
            >
              <svg className="drop-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 15.5V4m0 0L8.5 7.5M12 4l3.5 3.5" />
                <path d="M4.5 15.5v3a1.5 1.5 0 0 0 1.5 1.5h12a1.5 1.5 0 0 0 1.5-1.5v-3" />
              </svg>
              <span className="drop-title">
                Drop a transcript here, or <span className="link">browse</span>
              </span>
              <span className="drop-sub">Exports from Meet, Zoom or Teams</span>
              <input
                ref={inputRef}
                type="file"
                accept={ACCEPTED.join(",")}
                hidden
                onChange={(e) => accept(e.target.files?.[0])}
              />
            </label>
          )}

          <div className="fields">
            <div className="field">
              <label htmlFor="title">Title</label>
              <input
                id="title"
                className="input"
                placeholder="Defaults to the filename"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="occurred">
                Date <span className="optional">optional</span>
              </label>
              <input
                id="occurred"
                type="datetime-local"
                className="input"
                value={occurredAt}
                onChange={(e) => setOccurredAt(e.target.value)}
              />
            </div>
          </div>

          {error && <div className="alert alert-error">{error}</div>}

          <div className="form-foot">
            <p className="form-note">
              {busy
                ? "Reading the transcript and writing the minutes…"
                : "Minutes are generated on upload and take a few seconds."}
            </p>
            <button type="submit" className="btn btn-primary" disabled={!file || busy}>
              {busy && <span className="spinner" />}
              {busy ? "Processing" : "Upload"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
