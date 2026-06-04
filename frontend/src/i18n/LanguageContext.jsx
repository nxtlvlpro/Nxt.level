import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { TRANSLATIONS, DEFAULT_LANG, SUPPORTED_LANGS } from "./translations";

const STORAGE_KEY = "nxt8.lang";

const LanguageContext = createContext({
  lang: DEFAULT_LANG,
  setLang: () => {},
  t: (key) => key,
});

// Inferring the user's preferred UI language on a fresh visit:
// 1. Honour a stored override (set via the burger menu).
// 2. Otherwise read the browser's `navigator.languages` / `navigator.language`
//    and pick the first supported match (BCP-47 → 2-letter code).
// 3. Fall back to DEFAULT_LANG.
function detectLang() {
  if (typeof window === "undefined") return DEFAULT_LANG;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && SUPPORTED_LANGS.includes(stored)) return stored;
  } catch {
    /* ignore */
  }
  try {
    const cands =
      (typeof navigator !== "undefined" && navigator.languages) ||
      (typeof navigator !== "undefined" && navigator.language && [navigator.language]) ||
      [];
    for (const raw of cands) {
      if (!raw) continue;
      const code = String(raw).toLowerCase().split(/[-_]/)[0];
      if (SUPPORTED_LANGS.includes(code)) return code;
    }
  } catch {
    /* ignore */
  }
  return DEFAULT_LANG;
}

function readStored() {
  return detectLang();
}

function writeStored(lang) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* ignore */
  }
}

function interpolate(str, vars) {
  if (!vars) return str;
  return str.replace(/\{(\w+)\}/g, (_, k) =>
    Object.prototype.hasOwnProperty.call(vars, k) ? String(vars[k]) : `{${k}}`
  );
}

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(() => readStored());

  useEffect(() => {
    writeStored(lang);
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("lang", lang);
    }
  }, [lang]);

  const setLang = useCallback((next) => {
    if (SUPPORTED_LANGS.includes(next)) setLangState(next);
  }, []);

  const t = useCallback(
    (key, vars) => {
      const dict = TRANSLATIONS[lang] || TRANSLATIONS[DEFAULT_LANG];
      const raw = dict[key] ?? TRANSLATIONS[DEFAULT_LANG][key] ?? key;
      return interpolate(raw, vars);
    },
    [lang]
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);

  return (
    <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
  );
}

export function useT() {
  return useContext(LanguageContext);
}

export default LanguageContext;
