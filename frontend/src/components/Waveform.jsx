import React, { useEffect, useRef } from "react";

// Lightweight bar-style waveform fed by the Web Audio AnalyserNode.
// Accepts ONE of:
//   - stream:  MediaStream (live microphone capture during recording)
//   - audio:   HTMLAudioElement (currently-playing TTS audio chunk)
// When neither is set, the bars sit flat at the baseline.
//
// Designed to be cheap: one AudioContext per host component instance,
// one Analyser per source, rAF render loop. Auto-tears-down on unmount.

const BARS = 9;
const FFT_SIZE = 128;

export default function Waveform({
  stream,
  audio,
  active = false,
  color = "var(--brand-turquoise)",
  height = 28,
  testId = "waveform",
}) {
  const ctxRef = useRef(null);
  const analyserRef = useRef(null);
  const srcRef = useRef(null);
  const rafRef = useRef(0);
  const barsRef = useRef([]);
  const dataRef = useRef(new Uint8Array(FFT_SIZE / 2));

  // Lazy create / resume the shared AudioContext.
  // Recovers from StrictMode cleanup (which closes the previous context)
  // by detecting the "closed" state and minting a fresh one.
  const ensureCtx = () => {
    const existing = ctxRef.current;
    if (!existing || existing.state === "closed") {
      const AC = window.AudioContext || window.webkitAudioContext;
      ctxRef.current = new AC();
    }
    if (ctxRef.current.state === "suspended") {
      ctxRef.current.resume().catch(() => {});
    }
    return ctxRef.current;
  };

  // Connect the proper source whenever `stream` or `audio` changes.
  useEffect(() => {
    const ctx = ensureCtx();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = FFT_SIZE;
    analyser.smoothingTimeConstant = 0.75;
    analyserRef.current = analyser;
    dataRef.current = new Uint8Array(analyser.frequencyBinCount);

    let source = null;
    try {
      if (stream) {
        source = ctx.createMediaStreamSource(stream);
        source.connect(analyser);
      } else if (audio) {
        // An HTMLMediaElement may only ever be passed to ONE source node.
        // We tag it so a second call doesn't crash with InvalidStateError.
        if (audio.__waveformSourceCtx === ctx) {
          source = audio.__waveformSource;
        } else {
          source = ctx.createMediaElementSource(audio);
          // eslint-disable-next-line no-param-reassign
          audio.__waveformSource = source;
          // eslint-disable-next-line no-param-reassign
          audio.__waveformSourceCtx = ctx;
          // Audio also needs to flow to the speakers.
          source.connect(ctx.destination);
        }
        source.connect(analyser);
      }
    } catch {
      // ignore — source already connected or unsupported media
    }
    srcRef.current = source;

    return () => {
      try {
        if (source && stream) source.disconnect(analyser);
        if (source && audio) source.disconnect(analyser);
      } catch {
        /* ignore */
      }
      analyserRef.current = null;
    };
  }, [stream, audio]);

  // Render loop.
  useEffect(() => {
    const tick = () => {
      const analyser = analyserRef.current;
      const els = barsRef.current;
      if (!analyser || els.length === 0) {
        rafRef.current = requestAnimationFrame(tick);
        return;
      }
      analyser.getByteFrequencyData(dataRef.current);
      const data = dataRef.current;
      const bins = data.length;
      const perBar = Math.floor(bins / BARS) || 1;
      for (let i = 0; i < BARS; i += 1) {
        let sum = 0;
        for (let j = 0; j < perBar; j += 1) {
          sum += data[i * perBar + j] || 0;
        }
        const avg = sum / perBar;
        // Map 0..255 → 0..1 with a gentle floor so idle bars aren't 0px.
        const norm = Math.max(0.08, Math.min(1, avg / 220));
        const h = Math.round(norm * height);
        const el = els[i];
        if (el) el.style.height = `${h}px`;
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [height]);

  // Close the AudioContext on unmount to free resources. Also null the
  // ref so a re-mount (e.g. React 18 StrictMode double-invoke) doesn't
  // accidentally reuse the now-closed context.
  useEffect(
    () => () => {
      try {
        if (ctxRef.current) ctxRef.current.close().catch(() => {});
      } catch {
        /* ignore */
      }
      ctxRef.current = null;
    },
    []
  );

  const bars = Array.from({ length: BARS }, (_, i) => i);

  return (
    <div
      className="flex items-end justify-center gap-1"
      style={{ height }}
      data-testid={testId}
      data-active={active ? "1" : "0"}
    >
      {bars.map((i) => (
        <span
          key={i}
          ref={(el) => {
            barsRef.current[i] = el;
          }}
          className={`w-1 rounded-full transition-[opacity] ${
            active ? "opacity-100" : "opacity-40"
          }`}
          style={{
            height: "3px",
            background: color,
            boxShadow: active ? `0 0 6px ${color}` : "none",
          }}
        />
      ))}
    </div>
  );
}
