// TelegramConnectCard — 1-click bind of the user's Telegram chat
// to their NXT8 user_id. Reuses the same anonymous identity that the
// Hermes web chat uses (localStorage key: "nxt8.user_id"), so binding
// done here works for the chat toolbar button too.
//
// On click → backend mints a one-time deep-link → we open t.me/<bot>?start=<token>
// in a new tab → user presses Start → webhook binds the chat → we poll
// /telegram/status until connected and update the UI.

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Send,
  CheckCircle2,
  Loader2,
  Link as LinkIcon,
  Unplug,
  Copy,
  Check,
} from "lucide-react";
import CollapsibleCard from "../CollapsibleCard";
import api from "../../lib/api";

const NXT8_USER_ID_KEY = "nxt8.user_id";

function ensureClientId() {
  if (typeof window === "undefined") return "anon";
  try {
    let uid = localStorage.getItem(NXT8_USER_ID_KEY);
    if (!uid) {
      uid = `u_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem(NXT8_USER_ID_KEY, uid);
    }
    return uid;
  } catch {
    return "anon";
  }
}

export default function TelegramConnectCard() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [link, setLink] = useState(null);
  const [err, setErr] = useState(null);
  const [copied, setCopied] = useState(false);
  const pollRef = useRef(null);
  const clientId = ensureClientId();

  const refresh = useCallback(async () => {
    try {
      const s = await api.telegramStatus(clientId);
      setStatus(s);
      if (s?.connected) {
        setLink(null);
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      }
    } catch (e) {
      setErr(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    refresh();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [refresh]);

  const onConnect = async () => {
    setErr(null);
    try {
      const res = await api.telegramConnect(clientId);
      if (!res?.ok || !res.deep_link) {
        setErr(res?.error || "не удалось получить ссылку");
        return;
      }
      setLink(res);
      // Open the deep-link in a new tab. Some browsers block this if the
      // click isn't directly user-initiated, so we render a fallback link too.
      try {
        window.open(res.deep_link, "_blank", "noopener,noreferrer");
      } catch {
        /* fallback: user clicks the visible link below */
      }
      // Poll for binding (every 2s, 30 attempts = ~1 min).
      if (pollRef.current) clearInterval(pollRef.current);
      let ticks = 0;
      pollRef.current = setInterval(async () => {
        ticks += 1;
        await refresh();
        if (ticks > 30 && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      }, 2000);
    } catch (e) {
      setErr(e?.message || String(e));
    }
  };

  const onDisconnect = async () => {
    if (!window.confirm("Отвязать Telegram от вашего аккаунта?")) return;
    try {
      await api.telegramDisconnect(clientId);
      setLink(null);
      await refresh();
    } catch (e) {
      setErr(e?.message || String(e));
    }
  };

  const onCopy = async () => {
    if (!link?.deep_link) return;
    try {
      await navigator.clipboard.writeText(link.deep_link);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked */
    }
  };

  const enabled = status?.enabled !== false;
  const connected = !!status?.connected;
  const botUsername = status?.bot_username || link?.bot_username;

  return (
    <CollapsibleCard
      storageKey="agents-telegram-connect"
      testId="telegram-connect-card"
      title="Telegram — управляйте NXT8 из мессенджера"
      titleRight={
        connected ? (
          <span
            data-testid="telegram-state-connected"
            className="text-[10px] font-mono px-2 py-0.5 rounded-full ring-1 bg-emerald-500/15 ring-emerald-400/40 text-emerald-200"
          >
            CONNECTED
          </span>
        ) : (
          <span
            data-testid="telegram-state-disconnected"
            className="text-[10px] font-mono px-2 py-0.5 rounded-full ring-1 bg-white/5 ring-white/10 text-white/40"
          >
            OFF
          </span>
        )
      }
    >
      <div className="text-[11px] font-mono text-white/40 mb-3 leading-relaxed">
        Привяжите ваш Telegram к NXT8 в 1 клик. Hermes будет отвечать на сообщения,
        присылать карточки на одобрение с кнопками{" "}
        <span className="text-emerald-300">Approve</span> /{" "}
        <span className="text-rose-300">Reject</span> и алерты по ROI прямо в чат.
      </div>

      {!enabled && (
        <div
          className="text-xs text-amber-200 bg-amber-500/10 ring-1 ring-amber-400/30 rounded-lg p-3 font-mono mb-3"
          data-testid="telegram-disabled-banner"
        >
          Telegram-бот не настроен (нет TELEGRAM_BOT_TOKEN). Свяжитесь с
          администратором.
        </div>
      )}

      {err && (
        <div
          className="text-xs text-rose-300 bg-rose-500/10 ring-1 ring-rose-400/30 rounded-lg p-3 font-mono mb-3"
          data-testid="telegram-error"
        >
          {err}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-xs text-white/40 font-mono">
          <Loader2 className="w-3 h-3 animate-spin" /> загрузка…
        </div>
      )}

      {!loading && enabled && connected && (
        <div
          className="rounded-xl bg-emerald-500/10 ring-1 ring-emerald-400/30 p-4 flex items-start gap-3"
          data-testid="telegram-bound-panel"
        >
          <CheckCircle2 className="w-5 h-5 text-emerald-300 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-sm text-emerald-100">
              Подключено как{" "}
              <span className="font-mono">
                {status?.chat?.first_name || "Telegram user"}
                {status?.chat?.username ? ` @${status.chat.username}` : ""}
              </span>
            </div>
            <div className="text-[11px] font-mono text-white/40 mt-1">
              Бот: @{botUsername || "—"} · С{" "}
              {status?.chat?.bound_at
                ? new Date(status.chat.bound_at).toLocaleString()
                : "—"}
            </div>
          </div>
          <button
            type="button"
            data-testid="telegram-disconnect-btn"
            onClick={onDisconnect}
            className="inline-flex items-center gap-1 text-[11px] font-mono px-3 py-1.5 rounded-md bg-white/5 ring-1 ring-white/10 text-white/70 hover:bg-rose-500/10 hover:text-rose-200 hover:ring-rose-400/30 transition"
          >
            <Unplug className="w-3 h-3" /> Отвязать
          </button>
        </div>
      )}

      {!loading && enabled && !connected && (
        <div className="space-y-3">
          <button
            type="button"
            data-testid="telegram-connect-btn"
            onClick={onConnect}
            disabled={!enabled}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-sky-500/15 ring-1 ring-sky-400/40 text-sky-100 hover:bg-sky-500/25 transition font-medium disabled:opacity-40"
          >
            <Send className="w-4 h-4" /> Подключить Telegram в 1 клик
          </button>

          {link?.deep_link && (
            <div
              className="rounded-lg bg-white/[0.03] ring-1 ring-white/10 p-3 space-y-2"
              data-testid="telegram-deep-link-panel"
            >
              <div className="text-[11px] font-mono text-white/50">
                Если новая вкладка не открылась, перейдите вручную:
              </div>
              <div className="flex items-center gap-2">
                <a
                  href={link.deep_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  data-testid="telegram-deep-link"
                  className="inline-flex items-center gap-1 text-xs font-mono text-sky-300 hover:text-sky-200 truncate"
                >
                  <LinkIcon className="w-3 h-3 shrink-0" />
                  <span className="truncate">{link.deep_link}</span>
                </a>
                <button
                  type="button"
                  onClick={onCopy}
                  data-testid="telegram-copy-link"
                  className="ml-auto inline-flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded-md bg-white/5 ring-1 ring-white/10 text-white/60 hover:bg-white/10 transition"
                >
                  {copied ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-300" /> скопировано
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" /> копировать
                    </>
                  )}
                </button>
              </div>
              <div className="flex items-center gap-2 text-[10px] font-mono text-white/40">
                <Loader2 className="w-3 h-3 animate-spin" />
                ожидаем подтверждения в Telegram… (срок ссылки:{" "}
                {link.expires_in_minutes || 30} мин)
              </div>
            </div>
          )}
        </div>
      )}
    </CollapsibleCard>
  );
}
