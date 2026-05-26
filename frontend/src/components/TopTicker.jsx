import React, { useEffect, useRef, useState } from "react";

// ============================================================
// Live date/time helpers
// ============================================================

function formatDateParts(d) {
  // English locale to keep the ticker uniform regardless of UI language.
  const weekday = d
    .toLocaleDateString("en-US", { weekday: "long" })
    .toUpperCase();
  const month = d
    .toLocaleDateString("en-US", { month: "long" })
    .toUpperCase();
  const day = d.getDate();
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return {
    weekday,
    dateLine: `${month} ${day}`,
    time: `${hh}:${mm}`,
  };
}

function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

// ============================================================
// Build the ticker phrase list with per-phrase colors
// ============================================================

function buildPhrases({ weekday, dateLine, time, userName = "ALEX" }) {
  return [
    {
      text: `NXT8 // WELCOME, ${userName.toUpperCase()}`,
      color: "text-brand-turquoise",
    },
    // Single grouped pause phrase: weekday + date + time, no separators,
    // wide internal padding (rendered as a multi-colored composite).
    {
      pause: true,
      composite: [
        { text: weekday, color: "text-sky-400" },
        { text: dateLine, color: "text-purple-400" },
        { text: time, color: "text-orange-400" },
      ],
    },
    { text: "OPERATIONS CENTER ACTIVE", color: "text-emerald-400" },
    { text: "AI COORDINATION ENABLED", color: "text-brand-turquoise" },
    { text: "BUSINESS PROCESSES STABLE", color: "text-sky-400" },
    { text: "TEAM ONLINE", color: "text-emerald-400" },
    { text: "TASK MONITORING ACTIVE", color: "text-yellow-300" },
    { text: "SYSTEM READY FOR OPERATION", color: "text-brand-turquoise" },
    { text: "HAVE A GREAT DAY", color: "text-pink-400" },
  ];
}

// ============================================================
// Self-driven scroller with conditional pause at date/time
// ============================================================

const SPEED_PX_PER_SEC = 70;
const PAUSE_MS = 3000;
const SEPARATOR = "  •  ";

export default function TopTicker({ userName = "ALEX" }) {
  const now = useNow(1000);
  const parts = formatDateParts(now);
  const phrases = buildPhrases({ ...parts, userName });

  const containerRef = useRef(null);
  const trackRef = useRef(null);
  const offsetRef = useRef(0);
  const lastTsRef = useRef(0);
  const pauseUntilRef = useRef(0);
  // Track which pause-anchor elements (identified by their data-key) we've
  // already paused for in the current loop, so we don't pause again until
  // we wrap.
  const pausedKeysRef = useRef(new Set());
  const rafRef = useRef(0);
  const halfWidthRef = useRef(0);

  // Width (in px) of the currently-paused anchor — drives the side masks.
  // null while moving, number while paused.
  const [pausedAnchorWidth, setPausedAnchorWidth] = useState(null);
  const pauseTimeoutRef = useRef(null);

  // Recompute the inner track half-width whenever phrases change
  // (date/time updates every second).
  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    // The track holds two copies of the phrase set. Half its width is one
    // full loop length, which is where we reset offset to 0 for seamless wrap.
    halfWidthRef.current = track.scrollWidth / 2;
  }, [phrases.length, parts.time, parts.dateLine, parts.weekday]);

  useEffect(() => {
    const container = containerRef.current;
    const track = trackRef.current;
    if (!container || !track) return;

    const step = (ts) => {
      if (!lastTsRef.current) lastTsRef.current = ts;
      const dt = ts - lastTsRef.current;
      lastTsRef.current = ts;

      const now = performance.now();
      // Are we in a paused window?
      if (now < pauseUntilRef.current) {
        track.style.transform = `translateX(${offsetRef.current}px)`;
        rafRef.current = requestAnimationFrame(step);
        return;
      }

      // Advance offset (negative = scroll left).
      offsetRef.current -= (SPEED_PX_PER_SEC * dt) / 1000;

      // Seamless wrap once we've scrolled exactly one full set.
      if (-offsetRef.current >= halfWidthRef.current && halfWidthRef.current > 0) {
        offsetRef.current += halfWidthRef.current;
        pausedKeysRef.current.clear();
      }

      // Detect pause anchors crossing the container center.
      const containerRect = container.getBoundingClientRect();
      const centerX = containerRect.left + containerRect.width / 2;
      const anchors = track.querySelectorAll("[data-ticker-pause]");
      let triggeredKey = null;
      let triggeredWidth = 0;
      anchors.forEach((el) => {
        const key = el.getAttribute("data-pause-key");
        if (!key || pausedKeysRef.current.has(key)) return;
        // Use the inner text-only span (without the trailing separator) so
        // that "TUESDAY" itself ends up centered — not "TUESDAY  •  ".
        const inner = el.querySelector("[data-ticker-anchor-text]") || el;
        const r = inner.getBoundingClientRect();
        const elCenter = r.left + r.width / 2;
        // Trigger when the element's center is within 1px of container
        // center (i.e. just crossed it moving left).
        if (Math.abs(elCenter - centerX) <= Math.max(2, (SPEED_PX_PER_SEC * dt) / 1000 + 1)) {
          triggeredKey = key;
          triggeredWidth = r.width;
        }
      });
      if (triggeredKey) {
        pausedKeysRef.current.add(triggeredKey);
        pauseUntilRef.current = now + PAUSE_MS;
        setPausedAnchorWidth(triggeredWidth);
        if (pauseTimeoutRef.current) clearTimeout(pauseTimeoutRef.current);
        pauseTimeoutRef.current = setTimeout(() => {
          setPausedAnchorWidth(null);
        }, PAUSE_MS);
      }

      track.style.transform = `translateX(${offsetRef.current}px)`;
      rafRef.current = requestAnimationFrame(step);
    };

    rafRef.current = requestAnimationFrame(step);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (pauseTimeoutRef.current) clearTimeout(pauseTimeoutRef.current);
      lastTsRef.current = 0;
    };
  }, []);

  // Wide spacer used inside the date/weekday/time composite phrase.
  const INNER_PAD = "       "; // 7 spaces — empty visual buffer on each side
  const INNER_GAP = "     "; // 5 spaces — between weekday / date / time

  // Render two copies of the sequence end-to-end for the wrap.
  const renderSequence = (suffix) => (
    <span className="flex items-center" data-testid={`ticker-seq-${suffix}`}>
      {phrases.map((p, idx) => {
        const key = `${suffix}-${idx}`;
        const anchorAttrs = p.pause
          ? {
              "data-ticker-pause": "1",
              "data-pause-key": `${suffix}-${idx}`,
            }
          : {};

        if (p.composite) {
          // Composite (datetime) phrase: multi-colored, no • separators,
          // wide spaces inside; the whole block is one pause anchor.
          return (
            <span
              key={key}
              className="shrink-0 font-medium"
              {...anchorAttrs}
            >
              <span
                className="whitespace-pre"
                data-ticker-anchor-text={p.pause ? "1" : undefined}
              >
                <span className="text-slate-600">{INNER_PAD}</span>
                {p.composite.map((part, j) => (
                  <React.Fragment key={`${key}-c${j}`}>
                    <span className={part.color}>{part.text}</span>
                    {j < p.composite.length - 1 && (
                      <span className="text-slate-600">{INNER_GAP}</span>
                    )}
                  </React.Fragment>
                ))}
                <span className="text-slate-600">{INNER_PAD}</span>
              </span>
              {idx < phrases.length - 1 && (
                <span className="text-slate-600 whitespace-pre">{SEPARATOR}</span>
              )}
            </span>
          );
        }

        return (
          <span
            key={key}
            className={`shrink-0 ${p.color} font-medium`}
            {...anchorAttrs}
          >
            <span className="whitespace-pre" data-ticker-anchor-text={p.pause ? "1" : undefined}>
              {p.text}
            </span>
            {idx < phrases.length - 1 && (
              <span className="text-slate-600 whitespace-pre">{SEPARATOR}</span>
            )}
          </span>
        );
      })}
      {/* Tail separator before the next loop copy starts */}
      <span className="text-slate-600 whitespace-pre">{SEPARATOR}</span>
    </span>
  );

  // Mask width on each side during pause: covers everything outside a small
  // gutter around the centered anchor. ~10px gutter on each side feels right.
  const maskHalfClear =
    pausedAnchorWidth !== null ? pausedAnchorWidth / 2 + 10 : 0;
  const showMask = pausedAnchorWidth !== null;

  return (
    <nav
      ref={containerRef}
      className="relative z-10 px-4 py-2 border-b border-white/5 led-ticker overflow-hidden bg-brand-dark/80 backdrop-blur-md"
      data-testid="top-ticker"
    >
      <div
        ref={trackRef}
        className="flex items-center text-[11px] uppercase tracking-widest whitespace-nowrap will-change-transform"
        style={{ width: "max-content", transform: "translateX(0px)" }}
      >
        {renderSequence("a")}
        {renderSequence("b")}
      </div>

      {/* Side masks active only during the 3s pause — they hide neighboring
          phrases so only the date/weekday/time is visible. */}
      <div
        aria-hidden="true"
        data-testid="ticker-mask-left"
        className="pointer-events-none absolute top-0 bottom-0 left-0 bg-brand-dark transition-opacity duration-300 ease-out"
        style={{
          width: `calc(50% - ${maskHalfClear}px)`,
          opacity: showMask ? 1 : 0,
        }}
      />
      <div
        aria-hidden="true"
        data-testid="ticker-mask-right"
        className="pointer-events-none absolute top-0 bottom-0 right-0 bg-brand-dark transition-opacity duration-300 ease-out"
        style={{
          width: `calc(50% - ${maskHalfClear}px)`,
          opacity: showMask ? 1 : 0,
        }}
      />
    </nav>
  );
}
