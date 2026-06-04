// playStreamedTts.js
// Progressive playback of /api/voice/tts/stream via MediaSource API.
// Audio starts playing as soon as the first MP3 chunk arrives (~41 ms TTFB
// on Fish Audio), instead of waiting for the full file (~1.6 s).
//
// Falls back to a single Blob-based <audio> when MediaSource doesn't accept
// `audio/mpeg` (Firefox / older browsers). Returns a controller with
// `stop()` to cancel mid-playback.

const STREAM_MIME = "audio/mpeg";

export function playStreamedTts(text, { backendUrl, onStart, onEnd, onError, voice = "onyx", speed = 1.0 } = {}) {
  if (!text || !text.trim()) {
    onEnd?.();
    return { stop: () => {} };
  }
  const url = `${backendUrl}/api/voice/tts/stream`;
  const body = JSON.stringify({ text, voice, speed });
  const abort = new AbortController();

  const audio = new Audio();
  audio.autoplay = true;
  let stopped = false;
  let started = false;

  const cleanup = () => {
    try { audio.pause(); } catch { /* ignore */ }
    try { abort.abort(); } catch { /* ignore */ }
  };

  audio.addEventListener("playing", () => {
    if (!started) { started = true; onStart?.(audio); }
  });
  audio.addEventListener("ended", () => { if (!stopped) onEnd?.(); });
  audio.addEventListener("error", () => { if (!stopped) onError?.(new Error("audio element error")); });

  const supportsMs = typeof window !== "undefined"
    && "MediaSource" in window
    && window.MediaSource.isTypeSupported(STREAM_MIME);

  if (supportsMs) {
    const ms = new window.MediaSource();
    audio.src = URL.createObjectURL(ms);

    ms.addEventListener("sourceopen", async () => {
      let sb;
      try {
        sb = ms.addSourceBuffer(STREAM_MIME);
      } catch (e) {
        onError?.(e);
        return;
      }
      const queue = [];
      let appending = false;
      const flush = () => {
        if (appending || queue.length === 0 || sb.updating) return;
        appending = true;
        try { sb.appendBuffer(queue.shift()); } catch (e) { onError?.(e); }
      };
      sb.addEventListener("updateend", () => { appending = false; flush(); });

      try {
        const resp = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body,
          signal: abort.signal,
        });
        if (!resp.ok || !resp.body) {
          onError?.(new Error(`HTTP ${resp.status}`));
          try { ms.endOfStream("network"); } catch { /* ignore */ }
          return;
        }
        const reader = resp.body.getReader();
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          if (value && value.length) { queue.push(value); flush(); }
        }
        // Wait for all queued buffers to flush before ending the stream.
        const finish = () => {
          if (queue.length === 0 && !sb.updating) {
            try { ms.endOfStream(); } catch { /* ignore */ }
          } else {
            setTimeout(finish, 30);
          }
        };
        finish();
      } catch (e) {
        if (e?.name !== "AbortError") onError?.(e);
        try { ms.endOfStream("network"); } catch { /* ignore */ }
      }
    });
  } else {
    // Fallback: collect the whole body, then play via <audio>.
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      signal: abort.signal,
    })
      .then(async (resp) => {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const blob = await resp.blob();
        audio.src = URL.createObjectURL(blob);
      })
      .catch((e) => { if (e?.name !== "AbortError") onError?.(e); });
  }

  return {
    stop: () => { stopped = true; cleanup(); },
    audio,
  };
}
