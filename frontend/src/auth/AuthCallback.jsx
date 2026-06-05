// AuthCallback — handles the `#session_id=<id>` URL fragment returned by
// Emergent Google OAuth.
//
// Uses `useRef` (not state) to gate the one-shot exchange so React
// StrictMode's double-mount doesn't fire two POSTs.
//
// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT
// URLS, THIS BREAKS THE AUTH.

import React, { useEffect, useRef, useState } from "react";
import api from "../lib/api";
import { useUser, SESSION_TOKEN_KEY } from "./AuthContext";

export default function AuthCallback() {
  const hasProcessed = useRef(false);
  const { refresh } = useUser();
  const [error, setError] = useState(null);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = window.location.hash || "";
    const m = hash.match(/session_id=([^&]+)/);
    if (!m) {
      setError("session_id missing");
      return;
    }
    const sessionId = decodeURIComponent(m[1]);

    (async () => {
      try {
        const res = await api.authSession(sessionId);
        // Bearer-header fallback for environments that block 3rd-party cookies
        if (res?.session_token) {
          try {
            localStorage.setItem(SESSION_TOKEN_KEY, res.session_token);
          } catch {
            /* ignore */
          }
        }
        await refresh();
        // Strip the fragment + send the user into the app.
        window.history.replaceState({}, "", "/home");
        window.location.replace("/home");
      } catch (e) {
        setError(e?.response?.data?.detail || e?.message || "auth_failed");
      }
    })();
  }, [refresh]);

  return (
    <div
      data-testid="auth-callback-screen"
      className="min-h-screen flex flex-col items-center justify-center bg-brand-dark text-slate-200"
    >
      {error ? (
        <>
          <div className="text-rose-300 font-mono text-sm mb-3">
            ⚠ {String(error)}
          </div>
          <a
            href="/login"
            className="text-sky-300 underline text-xs"
            data-testid="auth-callback-retry"
          >
            Попробовать ещё раз
          </a>
        </>
      ) : (
        <>
          <div className="w-8 h-8 border-2 border-brand-turquoise border-t-transparent rounded-full animate-spin mb-4" />
          <div className="text-xs font-mono text-white/50">
            Подключаем ваш Google-аккаунт…
          </div>
        </>
      )}
    </div>
  );
}
