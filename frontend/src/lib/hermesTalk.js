// hermesTalk.js — client for /api/hermes/talk SSE stream.
//
// Calls the backend, parses interleaved `text`/`voice` events, accumulates
// the text reply and queues incoming MP3 sentence-blobs into a single
// HTMLAudioElement playlist so audio plays in order without gaps.
//
// Returns an object with:
//   onText(handler)   — called with each text delta
//   onVoice(handler)  — called when a new sentence audio starts playing
//   onDone(handler)   — called when stream completes
//   onError(handler)
//   stop()            — abort + flush audio queue

export function hermesTalk({ backendUrl, message, userId, sessionId, lang = "ru" }) {
  const listeners = { text: [], voice: [], done: [], error: [] };
  const on = (k) => (h) => listeners[k].push(h);
  const fire = (k, ...args) => listeners[k].forEach((h) => h(...args));

  const abort = new AbortController();
  const audio = new Audio();
  const queue = []; // Blob URLs to play in order
  let playing = false;
  let stopped = false;

  const playNext = () => {
    if (playing || queue.length === 0 || stopped) return;
    playing = true;
    audio.src = queue.shift();
    audio.play().catch(() => { /* autoplay block / cancel — ignore */ });
  };
  audio.addEventListener("ended", () => { playing = false; playNext(); });
  audio.addEventListener("error", () => { playing = false; playNext(); });

  const stop = () => {
    stopped = true;
    try { abort.abort(); } catch { /* ignore */ }
    try { audio.pause(); } catch { /* ignore */ }
    queue.length = 0;
  };

  (async () => {
    try {
      const resp = await fetch(`${backendUrl}/api/hermes/talk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          user_id: userId,
          session_id: sessionId,
          lang,
        }),
        signal: abort.signal,
      });
      if (!resp.ok || !resp.body) {
        fire("error", new Error(`HTTP ${resp.status}`));
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let bufStr = "";
      let curEvent = null;

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        bufStr += decoder.decode(value, { stream: true });

        // SSE frames are separated by \n. Parse complete lines.
        let nl;
        while ((nl = bufStr.indexOf("\n")) !== -1) {
          const line = bufStr.slice(0, nl);
          bufStr = bufStr.slice(nl + 1);
          if (!line) { curEvent = null; continue; }
          if (line.startsWith("event:")) {
            curEvent = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            const payload = line.slice(5).trim();
            if (!payload) continue;
            let data;
            try { data = JSON.parse(payload); } catch { continue; }
            if (curEvent === "text" && data.chunk) {
              fire("text", data.chunk);
            } else if (curEvent === "voice" && data.audio_b64) {
              try {
                const bin = atob(data.audio_b64);
                const arr = new Uint8Array(bin.length);
                for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
                const url = URL.createObjectURL(new Blob([arr], { type: "audio/mpeg" }));
                queue.push(url);
                fire("voice", { i: data.i, text: data.text, url });
                playNext();
              } catch (e) { fire("error", e); }
            } else if (curEvent === "done") {
              fire("done", data);
            } else if (curEvent === "error") {
              fire("error", new Error(data.message || "stream error"));
            }
          }
        }
      }
    } catch (e) {
      if (e?.name !== "AbortError") fire("error", e);
    }
  })();

  return {
    onText: on("text"),
    onVoice: on("voice"),
    onDone: on("done"),
    onError: on("error"),
    stop,
  };
}
