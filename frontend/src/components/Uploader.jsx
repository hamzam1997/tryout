import { useRef, useState } from "react";
import { loadDemoMeeting, uploadTranscript } from "../api";
import Icon from "./Icon";

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
  const [inFlight, setInFlight] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

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
    if (inputRef.current) inputRef.current.value = "";
  }

  function onDrop(event) {
    event.preventDefault();
    setDragging(false);
    accept(event.dataTransfer.files?.[0]);
  }

  async function onSubmit(event) {
    event.preventDefault();
    if (!file) return;

    // Capture then clear immediately so another file can be queued.
    const payload = { file, title, occurredAt };
    clear();
    setTitle("");
    setOccurredAt("");
    setError("");
    setNotice("");
    setInFlight((count) => count + 1);

    try {
      const result = await uploadTranscript(payload);
      onUploaded(result);
      if (result.duplicate) {
        setNotice(result.message || "This transcript was already uploaded.");
      }
    } catch (problem) {
      setError(problem.message);
    } finally {
      setInFlight((count) => Math.max(0, count - 1));
    }
  }

  async function handleLoadDemo() {
    setError("");
    setNotice("");
    setInFlight((count) => count + 1);
    try {
      const result = await loadDemoMeeting();
      clear();
      onUploaded(result);
      if (result.duplicate) {
        setNotice(result.message || "Demo transcript already loaded.");
      }
    } catch (problem) {
      setError(problem.message);
    } finally {
      setInFlight((count) => Math.max(0, count - 1));
    }
  }

  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h2>Upload a transcript</h2>
          <p className="card-hint">
            {ACCEPTED.join(", ")} up to 2 MB. Minutes and ideas process in the background.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          data-tour="load-demo"
          onClick={handleLoadDemo}
        >
          Load demo transcript
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
                <Icon name="close" />
              </button>
            </div>
          ) : (
            <label
              className={`drop${dragging ? " is-over" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
            >
              <span className="drop-icon"><Icon name="upload" size={18} /></span>
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
          {notice && !error && <div className="alert alert-ok">{notice}</div>}

          <div className="form-foot">
            <p className="form-note">You can queue another file as soon as this one is sent.</p>
            <button type="submit" className="btn btn-primary" disabled={!file}>
              Upload
            </button>
          </div>
        </form>

        {inFlight > 0 && (
          <p className="detail-note upload-inflight">
            {inFlight === 1
              ? "Sending transcript… it will appear in Recent below."
              : `Sending ${inFlight} transcripts… they will appear in Recent below.`}
          </p>
        )}
      </div>
    </div>
  );
}
