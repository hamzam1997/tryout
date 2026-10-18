import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Icon, { Logo } from "./Icon";
import { CHECKLIST, STAGE_NAMES } from "../lib/tour";

// Evaluator-only guide. It reads the workspace's real state, so each bubble appears
// because the evaluator did something (or a background job finished), not because
// a timer or a step counter moved on.

const BUBBLE_W = 320;
const GAP = 14;
const MARGIN = 12;

/* ── Sidebar checklist ───────────────────────────────── */

export function TourChecklist({ tour }) {
  if (!tour.enabled || tour.mode === null) return null;
  const doneCount = tour.flags.filter(Boolean).length;
  return (
    <section className="tour-guide" aria-label="Evaluator guide">
      <div className="tour-guide-head">
        <strong>Evaluator guide</strong>
        <span>{doneCount} of 5</span>
      </div>
      <ol>
        {CHECKLIST.map((label, i) => {
          const done = tour.flags[i];
          const current = !done && i === tour.stage;
          return (
            <li key={label} className={done ? "is-done" : current ? "is-current" : ""}>
              <span className="tour-guide-mark">{done ? <Icon name="check" size={10} /> : i + 1}</span>
              <span>{label}</span>
            </li>
          );
        })}
      </ol>
      {tour.mode === "paused" && tour.step && (
        <button type="button" className="btn btn-primary btn-sm" onClick={() => tour.setMode("guided")}>
          Resume guide
        </button>
      )}
    </section>
  );
}

/* ── Finding the target on the page ──────────────────── */

function sameAnchor(a, b) {
  return (
    a && b &&
    a.stepId === b.stepId &&
    a.cand === b.cand &&
    a.rect.top === b.rect.top && a.rect.left === b.rect.left &&
    a.rect.width === b.rect.width && a.rect.height === b.rect.height
  );
}

// Watches the page for the step's first visible target. Results are stamped with the
// step they were found for, so a stale position is never drawn for a newer step.
function useAnchor(step, active) {
  const [found, setFound] = useState(null);
  const [lostFor, setLostFor] = useState(null);

  useEffect(() => {
    if (!step || !active) return undefined;
    const stepId = step.id;
    let lastEl = null;
    let missingSince = null;

    function tick() {
      let hit = null;
      for (const cand of step.targets) {
        const el = document.querySelector(cand.sel);
        if (!el) continue;
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) continue;
        hit = { el, cand, r };
        break;
      }
      if (!hit) {
        missingSince = missingSince ?? Date.now();
        if (Date.now() - missingSince > 900) setLostFor(stepId);
        return;
      }
      missingSince = null;
      setLostFor(null);
      if (hit.el !== lastEl) {
        lastEl = hit.el;
        const offscreen = hit.r.top < 72 || hit.r.bottom > window.innerHeight - 40;
        if (offscreen && !hit.el.closest(".sidebar")) {
          hit.el.scrollIntoView({ block: "center", behavior: "smooth" });
        }
      }
      const next = {
        stepId,
        cand: hit.cand,
        rect: {
          top: Math.round(hit.r.top),
          left: Math.round(hit.r.left),
          width: Math.round(hit.r.width),
          height: Math.round(hit.r.height),
        },
      };
      setFound((prev) => (sameAnchor(prev, next) ? prev : next));
    }

    tick();
    const timer = setInterval(tick, 200);
    window.addEventListener("resize", tick);
    window.addEventListener("scroll", tick, true);
    return () => {
      clearInterval(timer);
      window.removeEventListener("resize", tick);
      window.removeEventListener("scroll", tick, true);
    };
  }, [step, active]);

  const anchor = active && step && found?.stepId === step.id ? found : null;
  const lost = active && step ? lostFor === step.id && !anchor : false;
  return { anchor, lost };
}

function placeBubble(rect, height) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const roomRight = vw - (rect.left + rect.width) - GAP - MARGIN;
  const roomBelow = vh - (rect.top + rect.height) - GAP - MARGIN;
  const roomAbove = rect.top - GAP - MARGIN;

  let side;
  if (rect.left < 280 && roomRight >= BUBBLE_W) side = "right";
  else if (roomBelow >= height) side = "bottom";
  else if (roomAbove >= height) side = "top";
  else if (roomRight >= BUBBLE_W) side = "right";
  else side = "left";

  let left;
  let top;
  if (side === "right") {
    left = rect.left + rect.width + GAP;
    top = rect.top + Math.min(rect.height / 2, 24) - 24;
  } else if (side === "left") {
    left = rect.left - GAP - BUBBLE_W;
    top = rect.top + Math.min(rect.height / 2, 24) - 24;
  } else {
    left = rect.left;
    top = side === "bottom" ? rect.top + rect.height + GAP : rect.top - GAP - height;
  }
  left = Math.max(MARGIN, Math.min(left, vw - BUBBLE_W - MARGIN));
  top = Math.max(MARGIN, Math.min(top, vh - height - MARGIN));

  // The arrow points at the target, whatever clamping did to the bubble.
  const vertical = side === "top" || side === "bottom";
  const along = vertical
    ? rect.left + Math.min(rect.width / 2, 48) - left
    : rect.top + Math.min(rect.height / 2, 24) - top;
  const arrow = Math.max(18, Math.min(along, (vertical ? BUBBLE_W : height) - 30));
  return { side, left, top, arrow };
}

/* ── Overlay: welcome, spotlight, bubble ─────────────── */

export function TourOverlay({ tour, suspended = false }) {
  const { enabled, mode, step } = tour;
  const guided = enabled && mode === "guided" && Boolean(step) && !suspended;
  const { anchor, lost } = useAnchor(step, guided);
  const bubbleRef = useRef(null);
  const arrowRef = useRef(null);

  // Position by measuring the real bubble, straight on the node: no extra render pass.
  useLayoutEffect(() => {
    const node = bubbleRef.current;
    if (!node) return;
    if (!anchor) {
      node.style.top = "";
      node.style.left = "";
      node.style.visibility = "visible";
      return;
    }
    const place = placeBubble(anchor.rect, node.offsetHeight);
    node.style.top = `${place.top}px`;
    node.style.left = `${place.left}px`;
    node.style.visibility = "visible";
    const arrow = arrowRef.current;
    if (arrow) {
      arrow.className = `tour-bubble-arrow is-${place.side}`;
      const vertical = place.side === "top" || place.side === "bottom";
      arrow.style.left = vertical ? `${place.arrow}px` : "";
      arrow.style.top = vertical ? "" : `${place.arrow}px`;
    }
  }, [anchor, step]);

  // Escape pauses the guide, unless a dialog (or the user's own typing) wants it.
  useEffect(() => {
    if (!guided) return undefined;
    function onKey(event) {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      if (document.querySelector("dialog[open]")) return;
      tour.setMode("paused");
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [guided, tour]);

  if (!enabled || suspended) return null;

  if (mode === null) {
    return (
      <div className="tour-welcome-backdrop">
        <div className="tour-welcome" role="dialog" aria-modal="true" aria-labelledby="tour-welcome-title">
          <Logo size={40} />
          <h2 id="tour-welcome-title">Welcome, evaluator</h2>
          <p>
            This is your own empty workspace. We&apos;ll guide you one action at a time: connect a
            demo repository, give it a meeting, approve an idea, and watch tryout attempt it.
          </p>
          <p className="tour-welcome-note">
            About 5 minutes, most of it tryout working in the background. Your progress stays in
            Evaluator guide in the sidebar.
          </p>
          <div className="tour-welcome-actions">
            <button type="button" className="btn btn-secondary" onClick={() => tour.setMode("paused")}>
              Explore on my own
            </button>
            <button type="button" className="btn btn-primary" autoFocus onClick={() => tour.setMode("guided")}>
              Guide me
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!guided || (!anchor && !lost)) return null;

  const cand = anchor?.cand ?? {};
  const title = cand.title ?? step.title;
  const body = cand.body ?? step.body;
  const hint = cand.hint ?? step.hint;
  const pad = 4;

  return (
    <>
      {anchor && (
        <div
          className={`tour-spot${step.kind === "wait" ? " is-wait" : ""}`}
          aria-hidden="true"
          style={{
            top: anchor.rect.top - pad,
            left: anchor.rect.left - pad,
            width: anchor.rect.width + pad * 2,
            height: anchor.rect.height + pad * 2,
          }}
        />
      )}
      <div
        ref={bubbleRef}
        className={`tour-bubble${anchor ? "" : " is-floating"}`}
        role="status"
        aria-live="polite"
        style={{ width: BUBBLE_W, visibility: "hidden" }}
        key={`${step.id}:${cand.sel ?? "none"}`}
      >
        {anchor && <span ref={arrowRef} className="tour-bubble-arrow" aria-hidden="true" />}
        <span className="tour-bubble-stage">
          {step.stage + 1} of 5 · {STAGE_NAMES[step.stage]}
        </span>
        <h2>{title}</h2>
        <p>{body}</p>

        {step.kind === "do" && hint && (
          <div className="tour-bubble-hint">
            <Icon name="arrowRight" size={14} />
            <span>{hint}</span>
          </div>
        )}
        {step.kind === "wait" && (
          <div className="tour-bubble-wait">
            <span className="spinner" />
            <div>
              <strong>{step.wait}</strong>
              <span>{step.note}</span>
            </div>
          </div>
        )}

        <div className="tour-bubble-foot">
          <button type="button" className="tour-bubble-skip" onClick={() => tour.setMode("paused")}>
            Skip guide
          </button>
          {step.kind === "info" && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={step.id === "map" ? tour.finish : tour.markReportSeen}
            >
              {step.next}
            </button>
          )}
        </div>
      </div>
    </>
  );
}
