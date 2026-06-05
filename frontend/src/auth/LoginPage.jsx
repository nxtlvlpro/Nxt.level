// LoginPage — Sign-in screen. One CTA: Google OAuth.

import React from "react";
import { useUser } from "./AuthContext";

export default function LoginPage() {
  const { login, user, loading } = useUser();

  // Already logged in → bounce to /home
  if (!loading && user && typeof window !== "undefined") {
    window.location.replace("/home");
    return null;
  }

  return (
    <div
      data-testid="login-screen"
      className="min-h-screen flex flex-col items-center justify-center bg-brand-dark text-slate-200 px-6"
    >
      <div className="max-w-md w-full text-center space-y-6">
        <div className="space-y-2">
          <div className="text-[11px] uppercase tracking-[0.3em] text-brand-turquoise">
            NXT8 · LOGIN
          </div>
          <h1 className="text-3xl sm:text-4xl font-semibold leading-tight">
            Войдите в NXT8
          </h1>
          <p className="text-sm text-white/50 leading-relaxed">
            AI-команда из 8 агентов. Hermes как CEO, HR, бухгалтерия,
            маркетинг, аналитика. Управляйте операционкой из мессенджера.
          </p>
        </div>

        <button
          type="button"
          onClick={login}
          data-testid="login-google-btn"
          className="w-full inline-flex items-center justify-center gap-3 px-6 py-3 rounded-xl bg-white text-slate-900 font-medium hover:bg-white/90 transition shadow-lg"
        >
          {/* Inline Google G mark — no extra asset needed */}
          <svg
            className="w-5 h-5"
            viewBox="0 0 48 48"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <path
              fill="#FFC107"
              d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.5-5.8 7.5-11.3 7.5-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.1 8.1 3l5.7-5.7C34.4 5.4 29.4 3 24 3 12.4 3 3 12.4 3 24s9.4 21 21 21 21-9.4 21-21c0-1.2-.1-2.4-.4-3.5z"
            />
            <path
              fill="#FF3D00"
              d="M6.3 14.7l6.6 4.8C14.7 16 19 13 24 13c3.1 0 5.9 1.1 8.1 3l5.7-5.7C34.4 5.4 29.4 3 24 3 16.3 3 9.7 7.4 6.3 14.7z"
            />
            <path
              fill="#4CAF50"
              d="M24 45c5.4 0 10.3-2.1 13.9-5.5l-6.4-5.4c-2 1.4-4.6 2.4-7.5 2.4-5.5 0-10.1-3.7-11.8-8.7L5.5 32.4C8.9 39.4 15.9 45 24 45z"
            />
            <path
              fill="#1976D2"
              d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4 5.6l6.4 5.4C41.4 36.4 45 30.9 45 24c0-1.2-.1-2.4-.4-3.5z"
            />
          </svg>
          Sign in with Google
        </button>

        <p className="text-[11px] font-mono text-white/30">
          Используем Emergent-managed OAuth · cookies httpOnly · 7-day session
        </p>
      </div>
    </div>
  );
}
