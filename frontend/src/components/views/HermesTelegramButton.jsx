// HermesTelegramButton — compact "Open in Telegram" pill that lives in
// the Hermes chat toolbar. Single-click flow:
//
//   • not connected → mint deep-link → open t.me/<bot>?start=<token> in a new tab,
//     start polling status until the chat is bound.
//   • already connected → open the persistent t.me/<bot> conversation directly.
//
// Identity: binds the Telegram chat to the SAME nxt8.user_id used by the
// web Hermes chat (HomeView). That way Hermes treats both channels as one
// user — shared memory, shared session, same persona.

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Send, CheckCircle2, Loader2 } from "lucide-react";
import api from "../../lib/api";

const NXT8_USER_ID_KEY = "nxt8.user_id";

function getOrCreateUserId() {
  if (typeof window === "undefined") return "anon";
  try {
    let uid = window.localStorage.getItem(NXT8_USER_ID_KEY);
    if (!uid) {
      uid = `u_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
      window.localStorage.setItem(NXT8_USER_ID_KEY, uid);
    }
    return uid;
  } catch {
    return "anon";
  }
}

export default function HermesTelegramButton() {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const pollRef = useRef(null);
  const clientId = getOrCreateUserId();

  const refresh = useCallback(async () => {
    try {
      const s = await api.telegramStatus(clientId);
      setStatus(s);
      if (s?.connected && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    } catch {
      /* silently ignore — button stays in initial state */
    }
  }, [clientId]);

  useEffect(() => {
    refresh();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [refresh]);

  const onClick = async () => {
    // Connected → just open the chat with the bot.
    if (status?.connected) {
      const username = status.bot_username;
      if (username) {
        window.open(`https://t.me/${username}`, "_blank", "noopener,noreferrer");
      }
      return;
    }
    // Not connected → mint deep-link and open it.
    setBusy(true);
    try {
      const res = await api.telegramConnect(clientId);
      if (res?.deep_link) {
        window.open(res.deep_link, "_blank", "noopener,noreferrer");
        // Poll status for ~1 min so the badge flips to "Connected" without
        // a page refresh once the user presses Start in Telegram.
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
      }
    } catch {
      /* surface nothing — the toolbar must stay clean */
    } finally {
      setBusy(false);
    }
  };

  // Don't render the button at all when the backend reports the bot is
  // disabled (no TELEGRAM_BOT_TOKEN in the env). Keeps the chat toolbar
  // honest in self-hosted setups.
  if (status && status.enabled === false) return null;

  const connected = !!status?.connected;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      data-testid="hermes-telegram-btn"
      title={
        connected
          ? "Открыть чат с Hermes в Telegram"
          : "Подключить Telegram — продолжить общение в мессенджере"
      }
      className={`px-3 py-1.5 rounded-full text-[10px] uppercase tracking-widest flex items-center gap-1.5 transition-colors border ${
        connected
          ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/20"
          : "border-sky-400/30 bg-sky-500/10 text-sky-200 hover:bg-sky-500/20"
      } disabled:opacity-40`}
    >
      {busy ? (
        <Loader2 className="w-3 h-3 animate-spin" />
      ) : connected ? (
        <CheckCircle2 className="w-3 h-3" />
      ) : (
        <Send className="w-3 h-3" />
      )}
      {connected ? "Telegram" : "В Telegram"}
    </button>
  );
}
