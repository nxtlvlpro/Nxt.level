import React, { useEffect, useRef, useState } from "react";
import { Mic, Square, Loader2, Volume2, AlertTriangle } from "lucide-react";
import api from "../../lib/api";
import CollapsibleCard from "../CollapsibleCard";
import { useT } from "../../i18n/LanguageContext";
import { hermesTalk } from "../../lib/hermesTalk";

const STATES = {
  IDLE: "idle",
  REQUESTING: "requesting",
  RECORDING: "recording",
  PROCESSING: "processing",
  SPEAKING: "speaking",
  ERROR: "error",
};

function pickMimeType() {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
    "audio/mp4",
  ];
  if (typeof window === "undefined" || !window.MediaRecorder) return "";
  return candidates.find((c) => window.MediaRecorder.isTypeSupported?.(c)) || "";
}

function filenameFromMime(mime) {
  if (!mime) return "speech.webm";
  if (mime.includes("webm")) return "speech.webm";
  if (mime.includes("ogg")) return "speech.ogg";
  if (mime.includes("mp4")) return "speech.mp4";
  return "speech.webm";
}

// Dev-only logger — silenced in production builds so internal failures
// don't leak to user devtools while preserving debugging signal locally.
function devError(scope, err) {
  if (process.env.NODE_ENV !== "production") {
    // eslint-disable-next-line no-console
    console.error(`MicView: ${scope}`, err);
  }
}

function renderMicIcon({ busy, recording, speaking }) {
  if (busy) {
    return (
      <Loader2
        className="w-10 h-10 text-brand-turquoise animate-spin"
        strokeWidth={1.5}
      />
    );
  }
  if (recording) {
    return (
      <Square
        className="w-9 h-9 text-red-300"
        strokeWidth={1.5}
        fill="currentColor"
      />
    );
  }
  if (speaking) {
    return <Volume2 className="w-10 h-10 text-brand-turquoise" strokeWidth={1.5} />;
  }
  return <Mic className="w-10 h-10 text-brand-turquoise" strokeWidth={1.5} />;
}

export default function MicView() {
  const { t, lang } = useT();
  const [state, setState] = useState(STATES.IDLE);
  const [error, setError] = useState("");
  const [transcript, setTranscript] = useState("");
  const [reply, setReply] = useState("");
  const [confidence, setConfidence] = useState(null);
  const [level, setLevel] = useState(0); // 0..1 input volume
  const sessionRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const rafRef = useRef(null);
  const audioElRef = useRef(null);
  const talkCtlRef = useRef(null);
  // VAD: auto-stop after sustained silence once user has actually spoken
  const SILENCE_THRESHOLD = 0.06; // input level (0..1) considered "silence"
  const SPEECH_THRESHOLD = 0.12; // input level that confirms user is speaking
  const SILENCE_HOLD_MS = 3000; // ms of continuous silence after speech before auto-submit
  const hasSpokenRef = useRef(false);
  const silenceStartRef = useRef(null);
  const autoStoppedRef = useRef(false);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      try {
        if (rafRef.current) cancelAnimationFrame(rafRef.current);
      } catch (err) {
        devError("cancelAnimationFrame failed", err);
      }
      try {
        streamRef.current?.getTracks().forEach((t) => t.stop());
      } catch (err) {
        devError("stream stop failed", err);
      }
      try {
        audioCtxRef.current?.close();
      } catch (err) {
        devError("audio context close failed", err);
      }
      try {
        talkCtlRef.current?.stop();
      } catch (err) {
        devError("talk stream stop failed", err);
      }
    };
  }, []);

  const stopMeter = () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    setLevel(0);
  };

  const startMeter = (stream) => {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      const ctx = new Ctx();
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      src.connect(analyser);
      audioCtxRef.current = ctx;
      analyserRef.current = analyser;
      const data = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / data.length);
        const lvl = Math.min(1, rms * 3);
        setLevel(lvl);

        // VAD: auto-submit after sustained silence once user has spoken
        if (!autoStoppedRef.current) {
          if (lvl >= SPEECH_THRESHOLD) {
            hasSpokenRef.current = true;
            silenceStartRef.current = null;
          } else if (hasSpokenRef.current && lvl < SILENCE_THRESHOLD) {
            const now = performance.now();
            if (silenceStartRef.current == null) {
              silenceStartRef.current = now;
            } else if (now - silenceStartRef.current >= SILENCE_HOLD_MS) {
              autoStoppedRef.current = true;
              try { stopRecording(); } catch (err) { devError("auto-stop failed", err); }
            }
          } else if (lvl >= SILENCE_THRESHOLD && lvl < SPEECH_THRESHOLD) {
            // intermediate level — keep current silence timer running (do nothing)
          }
        }
        rafRef.current = requestAnimationFrame(tick);
      };
      tick();
    } catch (err) {
      // meter is non-critical
      devError("audio meter init failed", err);
    }
  };

  const startRecording = async () => {
    setError("");
    setTranscript("");
    setReply("");
    setConfidence(null);
    setState(STATES.REQUESTING);
    // reset VAD state for a fresh utterance
    hasSpokenRef.current = false;
    silenceStartRef.current = null;
    autoStoppedRef.current = false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = pickMimeType();
      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => handleStop(mime);
      recorder.start();
      recorderRef.current = recorder;
      startMeter(stream);
      setState(STATES.RECORDING);
    } catch (e) {
      setError(e?.message || t("voice.error.mic"));
      setState(STATES.ERROR);
    }
  };

  const stopRecording = () => {
    try {
      recorderRef.current?.stop();
    } catch (err) {
      devError("recorder stop failed", err);
    }
    stopMeter();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setState(STATES.PROCESSING);
  };

  const handleStop = async (mime) => {
    try {
      const blob = new Blob(chunksRef.current, { type: mime || "audio/webm" });
      if (blob.size < 800) {
        setError(t("voice.too_short"));
        setState(STATES.ERROR);
        return;
      }
      const stt = await api.voiceStt(blob, {
        filename: filenameFromMime(mime),
        language: lang,
      });
      const transcriptText = (stt?.text || "").trim();
      if (!transcriptText) {
        setError(t("voice.too_short"));
        setState(STATES.ERROR);
        return;
      }

      setTranscript(transcriptText);
      setReply("");
      setConfidence(null);

      const ctl = hermesTalk({
        backendUrl: process.env.REACT_APP_BACKEND_URL,
        message: transcriptText,
        sessionId: sessionRef.current || undefined,
        lang,
      });
      talkCtlRef.current = ctl;
      let full = "";
      ctl.onText((delta) => {
        full += delta;
      });
      ctl.onVoice(() => {
        if (full.trim()) setReply(full.trim());
        setState(STATES.SPEAKING);
      });
      ctl.onDone(() => {
        if (full.trim()) setReply(full.trim());
        setState(STATES.IDLE);
      });
      ctl.onError((err) => {
        const msg = err?.message || "voice pipeline failed";
        setError(msg);
        setState(STATES.ERROR);
      });
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || "voice pipeline failed";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
      setState(STATES.ERROR);
    }
  };

  const busy = state === STATES.PROCESSING || state === STATES.REQUESTING;
  const recording = state === STATES.RECORDING;
  const speaking = state === STATES.SPEAKING;

  const onMainClick = () => {
    if (recording) return stopRecording();
    if (state === STATES.IDLE || state === STATES.ERROR) return startRecording();
  };

  const statusLabel = {
    [STATES.IDLE]: t("voice.status.idle"),
    [STATES.REQUESTING]: t("voice.status.requesting"),
    [STATES.RECORDING]: t("voice.status.recording"),
    [STATES.PROCESSING]: t("voice.status.processing"),
    [STATES.SPEAKING]: t("voice.status.speaking"),
    [STATES.ERROR]: t("voice.status.error"),
  }[state];

  // Build 24 bars for waveform-like UI
  const bars = Array.from({ length: 24 }, (_, i) => {
    const seed = Math.sin(i * 0.7) * 0.3 + 0.5;
    const h = recording ? Math.max(0.1, Math.min(1, level * (0.6 + seed * 0.8))) : 0.15 + seed * 0.1;
    return h;
  });

  return (
    <div className="lg:max-w-2xl lg:mx-auto">
      <CollapsibleCard
        storageKey="mic-voice"
        testId="mic-view"
      title={
        <span
          className="text-[10px] uppercase tracking-widest text-slate-400"
          data-testid="voice-status"
        >
          {statusLabel}
        </span>
      }
      titleRight={
        <span className="text-[10px] uppercase tracking-widest text-brand-turquoise/80">
          voice.module · whisper · tts
        </span>
      }
      bodyClassName="px-6 pb-6 pt-2"
    >
      <div className="flex flex-col items-center text-center space-y-5">
        <button
          onClick={onMainClick}
          disabled={busy || speaking}
          data-testid="mic-button"
          aria-label={recording ? t("voice.mic.aria.stop") : t("voice.mic.aria.start")}
          className={`relative w-28 h-28 rounded-full flex items-center justify-center transition-all
            ${recording ? "neo-icon-active animate-glow" : "neo-icon-active"}
            ${busy || speaking ? "opacity-60 cursor-not-allowed" : "hover:scale-[1.03] active:scale-[0.98]"}
          `}
        >
          <span
            className={`absolute inset-0 rounded-full ${recording ? "ring-2 ring-red-400/60" : "ring-1 ring-brand-turquoise/40"}`}
            style={recording ? { boxShadow: `0 0 ${10 + level * 40}px rgba(248,113,113,0.55)` } : undefined}
          />
          {renderMicIcon({ busy, recording, speaking })}
        </button>

        <div className="w-full h-12 flex items-end justify-center gap-[3px]" data-testid="voice-waveform">
          {bars.map((h, i) => (
            <span
              key={`bar-${i}`}
              className={`w-[3px] rounded-full ${recording ? "bg-brand-turquoise" : "bg-brand-turquoise/30"}`}
              style={{ height: `${Math.round(h * 100)}%`, transition: "height 80ms linear" }}
            />
          ))}
        </div>

        <div className="w-full text-left space-y-3" data-testid="voice-result">
          {transcript && (
            <div className="rounded-lg border border-brand-turquoise/15 bg-black/30 p-3">
              <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-1">{t("voice.you_said")}</div>
              <div className="text-slate-200 text-sm" data-testid="voice-transcript">{transcript}</div>
            </div>
          )}
          {reply && (
            <div className="rounded-lg border border-brand-turquoise/25 bg-brand-turquoise/[0.04] p-3">
              <div className="text-[10px] uppercase tracking-widest text-brand-turquoise/80 mb-1 flex justify-between">
                <span>NXT8</span>
                {confidence !== null && (
                  <span data-testid="voice-confidence">conf {(confidence * 100).toFixed(0)}%</span>
                )}
              </div>
              <div className="text-slate-100 text-sm whitespace-pre-wrap" data-testid="voice-reply">{reply}</div>
            </div>
          )}
          {error && (
            <div
              className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 flex items-start gap-2 text-red-300 text-xs"
              data-testid="voice-error"
            >
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>

        <div className="text-[10px] text-slate-500 max-w-xs">
          {t("voice.module_caption")}
        </div>

        <audio ref={audioElRef} className="hidden" data-testid="voice-audio" />
      </div>
    </CollapsibleCard>
    </div>
  );
}
