// MobileChatView — single-purpose, full-screen client chat for mobile.
//
// Layout (uses dvh so the input stays parked above the iOS / Android keyboard):
//   ┌───────────────────────────────────────┐
//   │  Existing app shell header             │  (untouched)
//   ├───────────────────────────────────────┤
//   │  conversation (scroll, flex-grow)      │
//   ├───────────────────────────────────────┤
//   │  attachments preview (horizontal)      │
//   │  [📎] [textarea (1–5 rows)]  [▶]      │
//   └───────────────────────────────────────┘
//   ↓ App shell BottomNav (untouched)
//
// Desktop keeps the original `ChatView` card path — this component is only
// rendered on screens < lg.
//
// Why a new component (not a fork of `ChatPanel`):
//   • Mobile UX needs file attachments, attachment sheet, auto-grow textarea,
//     and a bottom-anchored input. Bolting all that into the legacy desktop
//     panel would hurt both surfaces.

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Send,
  Paperclip,
  X,
  Camera,
  Image as ImageIcon,
  FileText,
  Table,
  ShieldCheck,
  AlertTriangle,
  Loader2,
  Download,
} from "lucide-react";
import api from "../../lib/api";
import { useT } from "../../i18n/LanguageContext";

// ────────────────────────────────────────────────────────────────────────────
// Constants
// ────────────────────────────────────────────────────────────────────────────

const MAX_FILES = 5;
const MAX_FILE_MB = 20;
const MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024;

const ACCEPTED = {
  documents: ".pdf,.docx,.doc,.txt,.rtf",
  tables: ".xlsx,.xls,.csv",
  images: "image/jpeg,image/png,image/webp,image/heic,image/heif",
  camera: "image/*",
};

const IMAGE_EXT = /\.(jpe?g|png|webp|heic|heif)$/i;
const TABLE_EXT = /\.(xlsx|xls|csv)$/i;

function isImage(file) {
  return file.type?.startsWith?.("image/") || IMAGE_EXT.test(file.name || "");
}
function isTable(file) {
  return TABLE_EXT.test(file.name || "");
}

function shortName(name, max = 20) {
  if (!name) return "";
  if (name.length <= max) return name;
  const dot = name.lastIndexOf(".");
  if (dot < 0) return name.slice(0, max - 1) + "…";
  const ext = name.slice(dot);
  const stem = name.slice(0, max - 1 - ext.length);
  return `${stem}…${ext}`;
}

function confidenceClass(level) {
  if (level === "high") return "confidence-high";
  if (level === "medium") return "confidence-medium";
  return "confidence-low";
}

// Tiny inline markdown — bold / italic / inline-code / ordered+unordered lists.
// Intentionally conservative (no HTML, no images) so we don't pull a full md
// renderer into the bundle.
function renderMarkdown(text) {
  if (!text) return null;
  const lines = text.split("\n");
  const blocks = [];
  let listBuffer = [];
  let listOrdered = false;

  const flushList = (key) => {
    if (!listBuffer.length) return;
    const items = listBuffer.map((l, i) => (
      <li key={`${key}-li-${i}`} className="leading-snug">
        {inline(l)}
      </li>
    ));
    blocks.push(
      listOrdered ? (
        <ol key={key} className="list-decimal pl-5 space-y-0.5">{items}</ol>
      ) : (
        <ul key={key} className="list-disc pl-5 space-y-0.5">{items}</ul>
      )
    );
    listBuffer = [];
  };

  const inline = (s) => {
    // Apply in order: code → bold → italic. Returns an array of nodes.
    const tokens = [];
    const re = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*]+\*)|(_[^_]+_)/g;
    let last = 0;
    let m;
    let i = 0;
    while ((m = re.exec(s)) !== null) {
      if (m.index > last) tokens.push(s.slice(last, m.index));
      const raw = m[0];
      if (raw.startsWith("`")) {
        tokens.push(
          <code key={`c-${i++}`} className="px-1 py-px rounded bg-white/10 text-[11px] text-brand-turquoise font-mono">
            {raw.slice(1, -1)}
          </code>
        );
      } else if (raw.startsWith("**")) {
        tokens.push(<strong key={`b-${i++}`} className="font-semibold text-white">{raw.slice(2, -2)}</strong>);
      } else {
        tokens.push(<em key={`i-${i++}`} className="italic text-slate-200">{raw.slice(1, -1)}</em>);
      }
      last = re.lastIndex;
    }
    if (last < s.length) tokens.push(s.slice(last));
    return tokens.length ? tokens : s;
  };

  lines.forEach((raw, idx) => {
    const line = raw.trimEnd();
    const ol = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    const ul = /^\s*[-*•]\s+(.*)$/.exec(line);
    if (ol) {
      if (!listOrdered && listBuffer.length) flushList(`l-${idx}`);
      listOrdered = true;
      listBuffer.push(ol[1]);
      return;
    }
    if (ul) {
      if (listOrdered && listBuffer.length) flushList(`l-${idx}`);
      listOrdered = false;
      listBuffer.push(ul[1]);
      return;
    }
    if (listBuffer.length) flushList(`l-${idx}`);
    if (!line.trim()) {
      blocks.push(<div key={`sp-${idx}`} className="h-2" />);
      return;
    }
    blocks.push(
      <p key={`p-${idx}`} className="leading-relaxed">
        {inline(line)}
      </p>
    );
  });
  if (listBuffer.length) flushList("l-end");

  return <div className="space-y-1">{blocks}</div>;
}

function formatTime(iso) {
  try {
    const d = iso ? new Date(iso) : new Date();
    return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

// ────────────────────────────────────────────────────────────────────────────
// Attachment preview chip (above the textarea)
// ────────────────────────────────────────────────────────────────────────────

function AttachmentChip({ file, previewUrl, onRemove }) {
  const img = isImage(file);
  return (
    <div
      className="relative shrink-0 group"
      data-testid="attachment-chip"
    >
      {img ? (
        <div className="w-12 h-12 rounded-lg overflow-hidden ring-1 ring-white/15 bg-zinc-900">
          {previewUrl && (
            <img
              src={previewUrl}
              alt={file.name}
              className="w-full h-full object-cover"
            />
          )}
        </div>
      ) : (
        <div className="flex items-center gap-2 pl-2 pr-3 h-12 rounded-lg ring-1 ring-white/15 bg-zinc-900">
          {isTable(file) ? (
            <Table className="w-4 h-4 text-emerald-300 shrink-0" />
          ) : (
            <FileText className="w-4 h-4 text-brand-turquoise shrink-0" />
          )}
          <span className="text-[11px] font-mono text-white/85 max-w-[140px] truncate">
            {shortName(file.name)}
          </span>
        </div>
      )}
      <button
        type="button"
        onClick={onRemove}
        data-testid="attachment-remove"
        aria-label="remove attachment"
        className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-rose-500/90 hover:bg-rose-400 text-white grid place-items-center"
      >
        <X className="w-2.5 h-2.5" />
      </button>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Attachment bottom-sheet
// ────────────────────────────────────────────────────────────────────────────

function AttachSheet({ open, onClose, onPick }) {
  if (!open) return null;
  const items = [
    { key: "camera",   label: "Камера",            icon: Camera,    accept: ACCEPTED.camera,    capture: "environment" },
    { key: "gallery",  label: "Фото из галереи",   icon: ImageIcon, accept: ACCEPTED.images },
    { key: "document", label: "Документ",          icon: FileText,  accept: ACCEPTED.documents },
    { key: "table",    label: "Таблица",           icon: Table,     accept: ACCEPTED.tables },
  ];
  return (
    <div
      className="fixed inset-0 z-50 flex items-end"
      data-testid="attach-sheet"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full bg-zinc-950 ring-1 ring-white/10 rounded-t-2xl px-4 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="w-10 h-1 rounded-full bg-white/20 mx-auto mb-3" />
        <div className="text-[11px] uppercase tracking-widest text-white/40 mb-2 px-1">
          Прикрепить
        </div>
        <div className="grid grid-cols-2 gap-2">
          {items.map(({ key, label, icon: Icon, accept, capture }) => (
            <button
              key={key}
              type="button"
              data-testid={`attach-${key}`}
              onClick={() => onPick({ accept, capture })}
              className="flex items-center gap-3 px-3 py-3 rounded-xl bg-white/[0.04] ring-1 ring-white/10 hover:bg-white/[0.08] active:bg-white/[0.12] transition text-left"
            >
              <Icon className="w-5 h-5 text-brand-turquoise shrink-0" />
              <span className="text-[13px] text-white/90 font-mono tracking-tight">{label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Message bubble
// ────────────────────────────────────────────────────────────────────────────

function MessageBubble({ msg }) {
  const isUser = msg.role === "user";
  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start items-end gap-2"}`}
      data-testid={`mbl-msg-${msg.role}`}
    >
      {!isUser && (
        <div className="shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-brand-turquoise/30 to-cyan-700/30 ring-1 ring-brand-turquoise/40 grid place-items-center text-brand-turquoise text-[10px] font-mono">
          H
        </div>
      )}
      <div className={`flex flex-col ${isUser ? "items-end" : "items-start"} max-w-[85%]`}>
        {!isUser && msg.meta?.thinking && !msg.content && (
          <div className="rounded-2xl px-4 py-3 bg-white/[0.04] ring-1 ring-white/10">
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-turquoise/70 animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-1.5 h-1.5 rounded-full bg-brand-turquoise/70 animate-bounce" style={{ animationDelay: "120ms" }} />
              <span className="w-1.5 h-1.5 rounded-full bg-brand-turquoise/70 animate-bounce" style={{ animationDelay: "240ms" }} />
            </div>
          </div>
        )}
        {(msg.content || (isUser && (msg.attachments?.length ?? 0) > 0)) && (
          <div
            className={`rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed shadow-sm
              ${isUser
                ? "bg-brand-turquoise/20 text-white ring-1 ring-brand-turquoise/50 rounded-br-md max-w-full"
                : "bg-white/[0.05] text-white/90 ring-1 ring-white/10 rounded-bl-md max-w-full"}`}
          >
            {/* Attachments inside the bubble */}
            {isUser && msg.attachments?.length > 0 && (
              <div className={`flex flex-wrap gap-2 ${msg.content ? "mb-2" : ""}`}>
                {msg.attachments.map((a, i) => (
                  <BubbleAttachment key={`${a.name}-${i}`} att={a} />
                ))}
              </div>
            )}
            {isUser ? (
              <div className="whitespace-pre-wrap break-words">{msg.content}</div>
            ) : (
              <div className="break-words">
                {renderMarkdown(msg.content)}
                {msg.meta?.streaming && (
                  <span className="ml-0.5 inline-block w-1.5 h-3.5 bg-brand-turquoise animate-pulse align-middle" />
                )}
              </div>
            )}
          </div>
        )}
        <div className={`mt-1 flex items-center gap-2 text-[10px] font-mono text-white/35 px-1 ${isUser ? "" : "self-start"}`}>
          <span data-testid="msg-time">{formatTime(msg.ts)}</span>
          {!isUser && msg.meta && !msg.meta?.streaming && msg.content && (
            <>
              <span className={`px-1.5 py-px rounded ${confidenceClass(msg.meta.confidence_level)} bg-white/5`}>
                {Math.round((msg.meta.confidence || 0) * 100)}%
              </span>
              {msg.meta.should_escalate && (
                <span className="flex items-center gap-1 text-orange-300">
                  <AlertTriangle className="w-2.5 h-2.5" /> escalate
                </span>
              )}
              {msg.meta.verification_status === "verified" && (
                <ShieldCheck className="w-2.5 h-2.5 text-emerald-300" />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function BubbleAttachment({ att }) {
  if (att.kind === "image" && att.url) {
    return (
      <a
        href={att.url}
        target="_blank"
        rel="noopener noreferrer"
        className="block rounded-lg overflow-hidden ring-1 ring-white/10 w-full max-w-[260px]"
        data-testid="bubble-image"
      >
        <img src={att.url} alt={att.name} className="w-full h-auto object-cover" />
      </a>
    );
  }
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.06] ring-1 ring-white/10 max-w-full">
      {isTable({ name: att.name }) ? (
        <Table className="w-4 h-4 text-emerald-300 shrink-0" />
      ) : (
        <FileText className="w-4 h-4 text-brand-turquoise shrink-0" />
      )}
      <span className="text-[12px] font-mono text-white/85 truncate max-w-[180px]">
        {shortName(att.name, 24)}
      </span>
      {att.url && (
        <a
          href={att.url}
          target="_blank"
          rel="noopener noreferrer"
          download
          className="ml-1 p-1 rounded hover:bg-white/10 text-white/70"
          data-testid="bubble-download"
          aria-label="download"
        >
          <Download className="w-3.5 h-3.5" />
        </a>
      )}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Main component
// ────────────────────────────────────────────────────────────────────────────

export default function MobileChatView() {
  const { t, lang } = useT();
  const welcomeText = t("chat.welcome") || "Привет! Я Hermes — главный координатор NXT8.";

  const [messages, setMessages] = useState(() => [
    {
      id: "welcome",
      role: "assistant",
      content: welcomeText,
      ts: new Date().toISOString(),
      meta: { confidence: 0.95, confidence_level: "high", verification_status: "verified" },
    },
  ]);
  const [input, setInput] = useState("");
  const [files, setFiles] = useState([]);          // [{file, previewUrl}]
  const [sending, setSending] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [toast, setToast] = useState(null);

  const sessionRef = useRef(
    `mob_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
  );
  const scrollRef = useRef(null);
  const endRef = useRef(null);
  const textareaRef = useRef(null);
  const hiddenInputRef = useRef(null);
  const pendingPickerRef = useRef({ accept: "*/*", capture: undefined });

  // ── Auto-scroll to last message ────────────────────────────────────────
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  // ── Object-URL lifecycle for image previews ────────────────────────────
  useEffect(() => {
    return () => {
      files.forEach((f) => f.previewUrl && URL.revokeObjectURL(f.previewUrl));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Auto-grow textarea (1–5 rows) ──────────────────────────────────────
  const autoGrow = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const lineH = 20; // matches text-[14px] / leading-snug
    const max = lineH * 5 + 16;
    el.style.height = `${Math.min(el.scrollHeight, max)}px`;
  }, []);

  useEffect(() => { autoGrow(); }, [input, autoGrow]);

  // ── Toast helper ───────────────────────────────────────────────────────
  const showToast = useCallback((msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  }, []);

  // ── File handling ──────────────────────────────────────────────────────
  const acceptFiles = useCallback((fileList) => {
    const incoming = Array.from(fileList || []);
    if (!incoming.length) return;
    let next = [...files];
    for (const f of incoming) {
      if (next.length >= MAX_FILES) {
        showToast(`Максимум ${MAX_FILES} файлов за раз`);
        break;
      }
      if (f.size > MAX_FILE_BYTES) {
        showToast(`Файл слишком большой. Максимум ${MAX_FILE_MB}MB`);
        continue;
      }
      const previewUrl = isImage(f) ? URL.createObjectURL(f) : null;
      next.push({ file: f, previewUrl });
    }
    setFiles(next);
  }, [files, showToast]);

  const removeFile = (idx) => {
    setFiles((prev) => {
      const next = [...prev];
      const [removed] = next.splice(idx, 1);
      if (removed?.previewUrl) URL.revokeObjectURL(removed.previewUrl);
      return next;
    });
  };

  const openPicker = ({ accept, capture }) => {
    pendingPickerRef.current = { accept, capture };
    setSheetOpen(false);
    // Re-create the input on every open so the same file can be re-picked.
    setTimeout(() => hiddenInputRef.current?.click(), 30);
  };

  const onHiddenChange = (e) => {
    acceptFiles(e.target.files);
    e.target.value = "";
  };

  // ── Paste from clipboard ───────────────────────────────────────────────
  const onPaste = (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const picked = [];
    for (const it of items) {
      if (it.kind === "file") {
        const f = it.getAsFile();
        if (f) picked.push(f);
      }
    }
    if (picked.length) {
      e.preventDefault();
      acceptFiles(picked);
    }
  };

  // ── Upload all pending attachments → returns [{name, url, kind}] ────────
  const uploadAll = useCallback(async () => {
    if (!files.length) return [];
    const uploaded = [];
    for (const { file } of files) {
      try {
        const res = await api.attachmentUpload(file, {
          session_id: sessionRef.current,
        });
        uploaded.push({
          name: file.name,
          url: res?.url || res?.public_url || null,
          kind: isImage(file) ? "image" : isTable(file) ? "table" : "document",
          size: file.size,
          backend_id: res?.attachment_id || res?.id || null,
        });
      } catch {
        // Endpoint may not exist on every env — fall back to local preview only.
        uploaded.push({
          name: file.name,
          url: isImage(file) ? files.find((f) => f.file === file)?.previewUrl : null,
          kind: isImage(file) ? "image" : isTable(file) ? "table" : "document",
          size: file.size,
        });
      }
    }
    return uploaded;
  }, [files]);

  // ── Send ───────────────────────────────────────────────────────────────
  const send = async () => {
    const text = input.trim();
    if ((!text && !files.length) || sending) return;
    setSending(true);

    // Upload attachments first so the bubble shows real preview URLs.
    let attachments = [];
    try {
      attachments = await uploadAll();
    } catch {
      attachments = files.map(({ file, previewUrl }) => ({
        name: file.name,
        url: previewUrl,
        kind: isImage(file) ? "image" : isTable(file) ? "table" : "document",
      }));
    }

    const userId = `m-u-${Date.now()}`;
    const aiId   = `m-a-${Date.now()}`;
    const userMsg = {
      id: userId,
      role: "user",
      content: text,
      ts: new Date().toISOString(),
      attachments,
    };
    const aiMsg = {
      id: aiId,
      role: "assistant",
      content: "",
      ts: new Date().toISOString(),
      meta: { thinking: true, streaming: true, intent: "...", confidence: 0 },
    };
    setMessages((m) => [...m, userMsg, aiMsg]);
    setInput("");
    // Reset attachments — URLs now live inside the bubble or backend-served.
    setFiles((prev) => {
      prev.forEach((f) => f.previewUrl && URL.revokeObjectURL(f.previewUrl));
      return [];
    });

    let aggregated = "";
    const composed = attachments.length
      ? `${text}\n\n[Прикреплено: ${attachments.map((a) => a.name).join(", ")}]`.trim()
      : text;

    try {
      await api.chatStream(
        {
          user_id: "demo",
          session_id: sessionRef.current,
          message: composed,
          language: lang,
        },
        {
          onMeta: (m) => {
            setMessages((msgs) => msgs.map((x) =>
              x.id === aiId
                ? { ...x, meta: { ...x.meta, thinking: false, intent: m.intent || x.meta?.intent } }
                : x
            ));
          },
          onDelta: (chunk) => {
            aggregated += chunk;
            setMessages((msgs) => msgs.map((x) =>
              x.id === aiId ? { ...x, content: aggregated, meta: { ...x.meta, thinking: false } } : x
            ));
          },
          onDone: (payload) => {
            setMessages((msgs) => msgs.map((x) =>
              x.id === aiId
                ? {
                    ...x,
                    content: aggregated || (t("chat.empty_reply") || "(пустой ответ)"),
                    meta: {
                      ...x.meta,
                      thinking: false,
                      streaming: false,
                      confidence: payload.confidence ?? 0.8,
                      confidence_level: payload.confidence_level || "medium",
                      verification_status: payload.verification_status,
                      should_escalate: payload.should_escalate,
                      latency_ms: payload.latency_ms,
                    },
                  }
                : x
            ));
          },
          onError: () => {
            setMessages((msgs) => msgs.map((x) =>
              x.id === aiId
                ? {
                    ...x,
                    content: t("chat.error.connect", { err: "stream" }) || "Ошибка соединения. Попробуйте ещё раз.",
                    meta: { ...x.meta, thinking: false, streaming: false, should_escalate: true, confidence_level: "low" },
                  }
                : x
            ));
          },
        }
      );
    } catch {
      setMessages((msgs) => msgs.map((x) =>
        x.id === aiId
          ? { ...x, content: "Ошибка соединения. Попробуйте ещё раз.", meta: { ...x.meta, thinking: false, streaming: false } }
          : x
      ));
    } finally {
      setSending(false);
    }
  };

  const onKey = (e) => {
    // Mobile users almost always tap the Send button; desktop users
    // (≥ lg) hit the legacy ChatView, but we still honour Ctrl/⌘+Enter.
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      send();
    }
  };

  const canSend = useMemo(
    () => !sending && (input.trim().length > 0 || files.length > 0),
    [sending, input, files.length]
  );

  // ── Shell ──────────────────────────────────────────────────────────────
  //
  // The parent app shell already pins:
  //   • Header at the top (lg+ also shows sidebar)
  //   • BottomNav at the bottom on mobile
  //   • Provides `main` scroll container with `overflow-y-auto`
  //
  // We don't want `main` to scroll independently of our messages list —
  // so we render into a flex column that owns its own scrolling and
  // sits inside `main` flush to its edges (negative-margins eat the
  // standard `px-4 py-4` so the chat goes edge-to-edge on mobile).
  //
  // dvh keeps the input above the soft keyboard on iOS / Android.

  return (
    <div
      data-testid="mobile-chat-view"
      className="
        -mx-4 -my-4
        flex flex-col
        h-[calc(100dvh-180px)]
        min-h-[60vh]
        bg-zinc-950/40
      "
    >
      {/* ── Conversation ─────────────────────────────────────────────── */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto overscroll-contain px-3 pt-3 pb-2 space-y-3"
        data-testid="mobile-chat-scroll"
      >
        {messages.map((m) => (
          <MessageBubble key={m.id} msg={m} />
        ))}
        <div ref={endRef} />
      </div>

      {/* ── Attachments preview row ──────────────────────────────────── */}
      {files.length > 0 && (
        <div
          className="shrink-0 border-t border-white/5 bg-zinc-950/70 px-3 py-2"
          data-testid="mobile-chat-attachments"
        >
          <div className="flex gap-2 overflow-x-auto no-scrollbar">
            {files.map((f, i) => (
              <AttachmentChip
                key={`${f.file.name}-${i}`}
                file={f.file}
                previewUrl={f.previewUrl}
                onRemove={() => removeFile(i)}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Input bar ────────────────────────────────────────────────── */}
      <div
        className="shrink-0 border-t border-white/10 bg-zinc-950/90 backdrop-blur-sm
                   px-2 py-2"
        data-testid="mobile-chat-input-bar"
      >
        <div className="flex items-end gap-2">
          <button
            type="button"
            onClick={() => setSheetOpen(true)}
            data-testid="mobile-chat-attach"
            disabled={files.length >= MAX_FILES}
            className="shrink-0 w-10 h-10 grid place-items-center rounded-full
                       bg-white/[0.06] ring-1 ring-white/10 text-white/80
                       active:bg-white/[0.12] disabled:opacity-40"
            aria-label="attach"
          >
            <Paperclip className="w-5 h-5" />
          </button>

          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            onPaste={onPaste}
            onFocus={() => {
              // Snap scroll to bottom so the latest message stays above the keyboard.
              setTimeout(() => endRef.current?.scrollIntoView({ block: "end" }), 250);
            }}
            placeholder="Напишите Hermes..."
            rows={1}
            data-testid="mobile-chat-input"
            className="flex-1 resize-none bg-white/[0.05] ring-1 ring-white/10
                       focus:ring-brand-turquoise/50 outline-none
                       rounded-2xl px-3.5 py-2.5 text-[14px] leading-snug
                       text-white placeholder:text-white/35
                       max-h-[124px]"
          />

          <button
            type="button"
            onClick={send}
            disabled={!canSend}
            data-testid="mobile-chat-send"
            className={`shrink-0 w-10 h-10 grid place-items-center rounded-full transition
              ${canSend
                ? "bg-brand-turquoise text-zinc-950 shadow-[0_4px_18px_-6px_rgba(0,240,255,0.6)] active:scale-95"
                : "bg-white/[0.06] ring-1 ring-white/10 text-white/30"}`}
            aria-label="send"
          >
            {sending ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {/* ── Hidden file input (driven by the sheet) ──────────────────── */}
      <input
        ref={hiddenInputRef}
        type="file"
        multiple
        className="hidden"
        accept={pendingPickerRef.current.accept}
        {...(pendingPickerRef.current.capture
          ? { capture: pendingPickerRef.current.capture }
          : {})}
        onChange={onHiddenChange}
        data-testid="mobile-chat-file-input"
      />

      <AttachSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        onPick={openPicker}
      />

      {/* ── Toast ────────────────────────────────────────────────────── */}
      {toast && (
        <div
          className="fixed left-1/2 -translate-x-1/2 bottom-24 z-[60]
                     px-4 py-2 rounded-full bg-zinc-900 ring-1 ring-rose-400/40
                     text-[12px] font-mono text-rose-200 shadow-lg"
          data-testid="mobile-chat-toast"
        >
          {toast}
        </div>
      )}
    </div>
  );
}
