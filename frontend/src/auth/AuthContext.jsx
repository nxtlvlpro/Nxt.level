// AuthContext — React Context provider for the logged-in user.
//
// Source of truth: server-side `/api/auth/me` (validated via httpOnly
// `session_token` cookie). Bearer header fallback uses localStorage for
// browsers/webviews that can't read cookies.
//
// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT
// URLS — THIS BREAKS THE AUTH. Use `window.location.origin`.

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import api from "../lib/api";

const AuthContext = createContext({
  user: null,
  loading: true,
  refresh: () => {},
  login: () => {},
  logout: () => {},
});

const SESSION_TOKEN_KEY = "nxt8.session_token";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // null = checking, true|false = authed status known
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const res = await api.authMe();
      setUser(res?.user || null);
    } catch (_e) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // CRITICAL: skip /me when returning from Google OAuth so AuthCallback
    // can exchange the session_id FIRST and establish the cookie.
    if (
      typeof window !== "undefined" &&
      window.location.hash?.includes("session_id=")
    ) {
      setLoading(false);
      return;
    }
    refresh();
  }, [refresh]);

  const login = useCallback(() => {
    if (typeof window === "undefined") return;
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirect = window.location.origin + "/auth/callback";
    window.location.href =
      "https://auth.emergentagent.com/?redirect=" + encodeURIComponent(redirect);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.authLogout();
    } catch {
      /* even if backend fails, drop local state */
    }
    try {
      localStorage.removeItem(SESSION_TOKEN_KEY);
    } catch {
      /* ignore */
    }
    setUser(null);
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, refresh, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useUser() {
  return useContext(AuthContext);
}

export { SESSION_TOKEN_KEY };
