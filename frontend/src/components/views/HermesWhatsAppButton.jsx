// HermesWhatsAppButton — compact "Open in WhatsApp" pill in the Hermes
// chat toolbar. Mirrors HermesTelegramButton but routes through Twilio.
//
//   • not connected → mint deep-link → open wa.me/<from>?text=NXT8+<token>
//     in a new tab; poll status until the binding lands.
//   • already connected → open the existing wa.me/<from> chat directly.
//
// Uses the SAME nxt8.user_id as the web Hermes chat so the agent treats
// web + WhatsApp + Telegram as one identity.

import React, { useCallback, useEffect, useRef, useState } from "react";
import { MessageCircle, CheckCircle2, Loader2 } from "lucide-react";
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

export default function HermesWhatsAppButton() {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const pollRef = useRef(null);
  const clientId = getOrCreateUserId();

  const refresh = useCallback(async () => {
    try {
      const s = await api.whatsappStatus(clientId);
      setStatus(s);
      if (s?.connected && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    } catch {
      /* silent — the toolbar must stay clean */
    }
  }, [clientId]);

  useEffect(() => {
    refresh();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [refresh]);

  const onClick = async () => {
    if (status?.connected && status.from) {
      const num = String(status.from).replace(/^\+/, "");
      window.open(`https://wa.me/${num}`, "_blank", "noopener,noreferrer");
      return;
    }
    setBusy(true);
    try {
      const res = await api.whatsappConnect(clientId);
      if (res?.deep_link) {
        window.open(res.deep_link, "_blank", "noopener,noreferrer");
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
      /* surface nothing in toolbar */
    } finally {
      setBusy(false);
    }
  };

  // Hide button if WhatsApp is not configured server-side.
  if (status && status.enabled === false) return null;

  const connected = !!status?.connected;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      data-testid="hermes-whatsapp-btn"
      title={
        connected
          ? "Открыть чат с Hermes в WhatsApp"
          : "Подключить WhatsApp — продолжить общение в мессенджере"
      }
      className={`px-3 py-1.5 rounded-full text-[10px] uppercase tracking-widest flex items-center gap-1.5 transition-colors border ${
        connected
          ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/20"
          : "border-green-400/30 bg-green-500/10 text-green-200 hover:bg-green-500/20"
      } disabled:opacity-40`}
    >
      {busy ? (
        <Loader2 className="w-3 h-3 animate-spin" />
      ) : connected ? (
        <CheckCircle2 className="w-3 h-3" />
      ) : (
        <MessageCircle className="w-3 h-3" />
      )}
      {connected ? "WhatsApp" : "В WhatsApp"}
    </button>
  );
}
