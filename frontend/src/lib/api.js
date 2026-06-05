import axios from "axios";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const SESSION_TOKEN_KEY = "nxt8.session_token";

const http = axios.create({
  baseURL: API,
  timeout: 180000,
  // Send the httpOnly session_token cookie cross-origin.
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

// Inject Bearer header from localStorage as a fallback for browsers /
// webviews that strip the third-party httpOnly cookie. The backend
// accepts whichever arrives first.
http.interceptors.request.use((config) => {
  try {
    const tok = localStorage.getItem(SESSION_TOKEN_KEY);
    if (tok && !config.headers.Authorization) {
      config.headers.Authorization = `Bearer ${tok}`;
    }
  } catch {
    /* ignore — localStorage may be disabled */
  }
  return config;
});

// Global response interceptor:
//   • 401 → silent redirect to /login (no toast).
//   • 4xx / 5xx → user-friendly toast.error (Russian copy by default;
//     uses `error.response.data.detail` when the backend supplied one).
http.interceptors.response.use(
  (r) => r,
  (error) => {
    const status = error?.response?.status;
    const url = error?.config?.url || "";
    // Don't redirect during the OAuth bootstrap calls themselves —
    // that would create a loop.
    const isAuthCall = url.startsWith("/auth/");

    if (status === 401) {
      if (!isAuthCall && typeof window !== "undefined") {
        try {
          localStorage.removeItem(SESSION_TOKEN_KEY);
        } catch {
          /* ignore */
        }
        const path = window.location.pathname || "";
        if (!path.startsWith("/login") && !path.startsWith("/auth/")) {
          window.location.replace("/login");
        }
      }
      // Never toast on 401 — the redirect IS the UX signal.
      return Promise.reject(error);
    }

    // Skip toasts for cancelled / network-aborted requests — they're
    // usually the result of route changes, not real failures.
    if (!status || error?.code === "ERR_CANCELED") {
      return Promise.reject(error);
    }

    const detail = error?.response?.data?.detail;
    const detailStr =
      typeof detail === "string" && detail.trim() ? detail.trim() : null;

    let message = null;
    if (status === 400) message = detailStr || "Проверьте данные";
    else if (status === 403) message = detailStr || "Нет доступа";
    else if (status === 404) message = detailStr || "Не найдено";
    else if (status === 429)
      message = "Слишком много запросов, подождите минуту";
    else if (status >= 500) message = "Ошибка сервера, попробуйте позже";

    if (message) {
      try {
        toast.error(message);
      } catch {
        /* sonner not mounted yet — silent */
      }
    }

    return Promise.reject(error);
  }
);

export const api = {
  health: () => http.get("/health").then((r) => r.data),
  seed: () => http.post("/seed").then((r) => r.data),

  // Emergent Google OAuth — session lifecycle
  authSession: (sessionId) =>
    http
      .post("/auth/session", null, { headers: { "X-Session-ID": sessionId } })
      .then((r) => r.data),
  authMe: () => http.get("/auth/me").then((r) => r.data),
  authLogout: () => http.post("/auth/logout").then((r) => r.data),

  chat: (payload) => http.post("/chat", payload).then((r) => r.data),
  recentRequests: (limit = 10) =>
    http.get(`/requests?limit=${limit}`).then((r) => r.data),

  // Onboarding survey (Connect → 7-question intake → Hermes brief)
  onboardingInsight: (payload) =>
    http.post("/onboarding/insight", payload).then((r) => r.data),
  onboardingVerifyCode: (code) =>
    http.post("/onboarding/verify-code", { code }).then((r) => r.data),
  onboardingSaveProfile: (payload) =>
    http.post("/onboarding/profiles", payload).then((r) => r.data),
  onboardingBrief: (profileId) =>
    http.post(`/onboarding/brief/${profileId}`).then((r) => r.data),

  memoryStore: (payload) => http.post("/memory/store", payload).then((r) => r.data),
  memorySearch: (payload) => http.post("/memory/search", payload).then((r) => r.data),
  memoryList: (type, limit = 50) =>
    http
      .get(`/memory/list?${type ? `type=${type}&` : ""}limit=${limit}`)
      .then((r) => r.data),

  employees: () => http.get("/mentor/employees").then((r) => r.data),
  employeeSummary: (id) =>
    http.get(`/mentor/employees/${id}`).then((r) => r.data),
  patterns: () => http.get("/mentor/patterns").then((r) => r.data),
  detectPatterns: (id) => http.post(`/mentor/detect/${id}`).then((r) => r.data),

  roiDashboard: () => http.get("/roi/dashboard").then((r) => r.data),
  roiCurrent: () => http.get("/roi/current").then((r) => r.data),
  roiTrend: (hours = 24) =>
    http.get(`/roi/trend?hours=${hours}`).then((r) => r.data),

  alerts: (limit = 20) => http.get(`/alerts?limit=${limit}`).then((r) => r.data),

  // Cross-Department Coordinator
  crossDeptCoordinate: (payload) =>
    http.post("/cross-dept/coordinate", payload).then((r) => r.data),
  crossDeptTasks: (limit = 20) =>
    http.get(`/cross-dept/tasks?limit=${limit}`).then((r) => r.data),
  crossDeptDetect: (query) =>
    http
      .get(`/cross-dept/detect?query=${encodeURIComponent(query)}`)
      .then((r) => r.data),

  // Diagnostics
  diagnosticsScan: (params = {}) =>
    http.post("/diagnostics/scan", null, { params }).then((r) => r.data),
  diagnosticsList: (limit = 30) =>
    http
      .get(`/diagnostics/contradictions?limit=${limit}`)
      .then((r) => r.data),
  diagnosticsSummary: (window = 200) =>
    http.get(`/diagnostics/summary?window=${window}`).then((r) => r.data),

  // Skills
  skillsScan: () => http.post("/skills/scan").then((r) => r.data),
  skillsList: (enabled = false, limit = 100) =>
    http
      .get(`/skills?enabled=${enabled}&limit=${limit}`)
      .then((r) => r.data),
  skillsCreate: (payload) => http.post("/skills", payload).then((r) => r.data),
  skillsToggle: (skill_id, enabled) =>
    http
      .post(`/skills/${skill_id}/toggle?enabled=${enabled}`)
      .then((r) => r.data),

  // Market Radar
  marketSignals: (category, limit = 50) =>
    http
      .get(
        `/market/signals?${category ? `category=${category}&` : ""}limit=${limit}`
      )
      .then((r) => r.data),
  marketIngest: (payload) =>
    http.post("/market/signals", payload).then((r) => r.data),
  marketScan: (window_hours = 24) =>
    http
      .post(`/market/scan?window_hours=${window_hours}`)
      .then((r) => r.data),
  marketDigests: (limit = 10) =>
    http.get(`/market/digests?limit=${limit}`).then((r) => r.data),

  // Hermes Agent proxy (module 15)
  hermesHealth: () => http.get("/hermes/health").then((r) => r.data),
  hermesChat: (payload) =>
    http.post("/hermes/chat", payload).then((r) => r.data),
  hermesJobsList: () => http.get("/hermes/jobs").then((r) => r.data),
  hermesJobCreate: (payload) =>
    http.post("/hermes/jobs", payload).then((r) => r.data),

  // Personas Layer (8 marketing-aligned agents + tariff gate)
  personasList: (plan_id) =>
    http
      .get(`/personas${plan_id ? `?plan_id=${plan_id}` : ""}`)
      .then((r) => r.data),
  personaChat: (persona_id, payload) =>
    http
      .post(`/personas/${persona_id}/chat`, payload, {
        // 402 (tariff gate) is expected — let frontend handle it
        validateStatus: (s) => s < 500,
      })
      .then((r) => ({ status: r.status, data: r.data })),

  // Inter-agent dialogues & escalations (CEO ↔ team)
  agentDialogues: (limit = 50, agent_id) =>
    http
      .get(`/agents/dialogues?limit=${limit}${agent_id ? `&agent_id=${agent_id}` : ""}`)
      .then((r) => r.data),
  agentEscalations: (limit = 50, status) =>
    http
      .get(`/agents/escalations?limit=${limit}${status ? `&status=${status}` : ""}`)
      .then((r) => r.data),

  // Approval Gate — high-impact actions waiting for Hermes/owner review
  approvalsList: (status = "pending", agent_id, limit = 50) =>
    http
      .get(
        `/approvals?status=${encodeURIComponent(status)}&limit=${limit}${agent_id ? `&agent_id=${encodeURIComponent(agent_id)}` : ""}`
      )
      .then((r) => r.data),
  approvalsApprove: (approval_id, decided_by = "owner", reason) =>
    http
      .post(`/approvals/${approval_id}/approve`, { decided_by, reason })
      .then((r) => r.data),
  approvalsReject: (approval_id, decided_by = "owner", reason) =>
    http
      .post(`/approvals/${approval_id}/reject`, { decided_by, reason })
      .then((r) => r.data),
  approvalsStats: (window_hours = 24) =>
    http
      .get(`/approvals/stats?window_hours=${window_hours}`)
      .then((r) => r.data),

  // Demo Tour — landing-page "Test Drive" checklist + funnel analytics
  tourCatalogue: () => http.get("/tour/catalogue").then((r) => r.data),
  tourEvent: (client_id, event, step_id, metadata) =>
    http
      .post("/tour/events", { client_id, event, step_id, metadata })
      .then((r) => r.data)
      .catch(() => ({ ok: false })),  // analytics must never break UX
  tourFunnel: (window_hours = 168) =>
    http.get(`/tour/funnel?window_hours=${window_hours}`).then((r) => r.data),

  // Share-My-Journey — viral channel after the Test Drive
  shareMint: (client_id, completed_steps, headline, locale = "ru") =>
    http
      .post("/share/journey", { client_id, completed_steps, headline, locale })
      .then((r) => r.data),
  shareGet: (share_id, ref) =>
    http
      .get(`/share/${encodeURIComponent(share_id)}${ref ? `?ref=${encodeURIComponent(ref)}` : ""}`)
      .then((r) => r.data),
  shareConversion: (share_id, kind = "checkout") =>
    http
      .post("/share/conversion", { share_id, kind })
      .then((r) => r.data)
      .catch(() => ({ ok: false })),
  shareStats: (window_hours = 24 * 30) =>
    http.get(`/share/stats?window_hours=${window_hours}`).then((r) => r.data),

  // Telegram channel — 1-click bot link for clients
  telegramStatus: () => http.get("/telegram/status").then((r) => r.data),
  telegramConnect: () => http.post("/telegram/connect", {}).then((r) => r.data),
  telegramDisconnect: () =>
    http.post("/telegram/disconnect", {}).then((r) => r.data),

  // WhatsApp channel — 1-click bind via wa.me deep-link (Twilio)
  whatsappStatus: () => http.get("/whatsapp/status").then((r) => r.data),
  whatsappConnect: () => http.post("/whatsapp/connect", {}).then((r) => r.data),
  whatsappDisconnect: () =>
    http.post("/whatsapp/disconnect", {}).then((r) => r.data),

  // Documents (Compliance persona)
  documentsList: (company_id, limit = 50) =>
    http
      .get(
        `/documents?${company_id ? `company_id=${company_id}&` : ""}limit=${limit}`
      )
      .then((r) => r.data),
  documentGet: (document_id) =>
    http.get(`/documents/${document_id}`).then((r) => r.data),
  documentUpload: (file, opts = {}) => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    if (opts.company_id) fd.append("company_id", opts.company_id);
    if (opts.user_id) fd.append("user_id", opts.user_id);
    if (opts.title) fd.append("title", opts.title);
    if (opts.notes) fd.append("notes", opts.notes);
    return http
      .post("/documents/upload", fd, {
        headers: { "Content-Type": undefined },
        timeout: 180000,
      })
      .then((r) => r.data);
  },

  // Universal chat attachments (paperclip in HomeView dialog).
  // Accepts any file; backend routes docs through Compliance + images
  // through OpenAI Vision and returns a chip-friendly record.
  attachmentUpload: (file, opts = {}) => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    if (opts.company_id) fd.append("company_id", opts.company_id);
    if (opts.user_id) fd.append("user_id", opts.user_id);
    if (opts.session_id) fd.append("session_id", opts.session_id);
    return http
      .post("/attachments/upload", fd, {
        headers: { "Content-Type": undefined },
        timeout: 180000,
      })
      .then((r) => r.data);
  },
  attachmentRawUrl: (id) =>
    `${http.defaults.baseURL}/attachments/${id}/raw`,

  // Payments — Stripe Checkout Sessions
  checkoutPlans: () => http.get("/payments/plans").then((r) => r.data),
  checkoutSessionCreate: (payload) =>
    http.post("/payments/checkout/session", payload).then((r) => r.data),
  checkoutStatus: (session_id) =>
    http.get(`/payments/checkout/status/${session_id}`).then((r) => r.data),

  voiceConverse: (blob, opts = {}) => {
    const fd = new FormData();
    const filename = opts.filename || "speech.webm";
    fd.append("file", blob, filename);
    if (opts.session_id) fd.append("session_id", opts.session_id);
    if (opts.user_id) fd.append("user_id", opts.user_id);
    if (opts.language) fd.append("language", opts.language);
    if (opts.voice) fd.append("voice", opts.voice);
    return http
      .post("/voice/converse", fd, {
        headers: { "Content-Type": undefined },
        timeout: 60000,
      })
      .then((r) => r.data);
  },

  // Streaming voice converse — NDJSON. Calls onFrame(frame) for each chunk.
  // Frame types: meta, transcript, reply_text, audio_chunk, done, error.
  voiceConverseStream: async (blob, opts = {}, onFrame) => {
    const fd = new FormData();
    const filename = opts.filename || "speech.webm";
    fd.append("file", blob, filename);
    if (opts.session_id) fd.append("session_id", opts.session_id);
    if (opts.user_id) fd.append("user_id", opts.user_id);
    if (opts.language) fd.append("language", opts.language);
    if (opts.voice) fd.append("voice", opts.voice);

    const ctrl = opts.signal ? undefined : new AbortController();
    const signal = opts.signal || ctrl?.signal;

    const resp = await fetch(`${API}/voice/converse_stream`, {
      method: "POST",
      body: fd,
      signal,
    });
    if (!resp.ok || !resp.body) {
      throw new Error(`voice_stream_failed_${resp.status}`);
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let nl;
      // eslint-disable-next-line no-cond-assign
      while ((nl = buf.indexOf("\n")) !== -1) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line) continue;
        try {
          const frame = JSON.parse(line);
          onFrame?.(frame);
        } catch {
          /* ignore malformed line */
        }
      }
    }
    if (buf.trim()) {
      try {
        onFrame?.(JSON.parse(buf.trim()));
      } catch {
        /* ignore */
      }
    }
  },

  voiceStt: (blob, opts = {}) => {
    const fd = new FormData();
    fd.append("file", blob, opts.filename || "speech.webm");
    if (opts.language) fd.append("language", opts.language);
    return http
      .post("/voice/stt", fd, {
        headers: { "Content-Type": undefined },
        timeout: 60000,
      })
      .then((r) => r.data);
  },

  // Server-Sent Events stream of /api/chat/stream.
  // onMeta({session_id, intent}), onDelta(text), onDone(payload), onError(msg)
  chatStream: async (payload, { onMeta, onDelta, onDone, onError, signal } = {}) => {
    const res = await fetch(`${API}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(payload),
      signal,
    });
    if (!res.ok || !res.body) {
      onError?.(`HTTP ${res.status}`);
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        let event = "message";
        let dataLine = "";
        for (const line of frame.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) dataLine += line.slice(5).trim();
        }
        if (!dataLine) continue;
        let data;
        try {
          data = JSON.parse(dataLine);
        } catch {
          continue;
        }
        if (event === "meta") onMeta?.(data);
        else if (event === "delta") onDelta?.(data.text || "");
        else if (event === "done") onDone?.(data);
        else if (event === "error") onError?.(data.message || "error");
      }
    }
  },

  // ---------- Hermes Operating Graph (10-node OS) ----------
  hermesOsNodes: () => http.get("/hermes/os/nodes").then((r) => r.data),
  hermesOsCycles: (limit = 20) =>
    http.get(`/hermes/os/cycles?limit=${limit}`).then((r) => r.data),
  hermesOsCycleGet: (cycle_id) =>
    http.get(`/hermes/os/cycle/${cycle_id}`).then((r) => r.data),
  hermesOsMemoryStats: () =>
    http.get("/hermes/memory/stats").then((r) => r.data),
  hermesOsMemoryKG: (entity, limit = 25) =>
    http
      .get(`/hermes/memory/knowledge-graph?${
        entity ? `entity=${encodeURIComponent(entity)}&` : ""
      }limit=${limit}`)
      .then((r) => r.data),
  hermesOsMemoryInst: (limit = 25) =>
    http.get(`/hermes/memory/institutional?limit=${limit}`).then((r) => r.data),
  // Live cycle SSE — calls onEvent(name, data) for every node tick.
  hermesOsStream: async (payload, onEvent) => {
    const resp = await fetch(`${API}/hermes/os/cycle/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    if (!resp.ok || !resp.body) {
      onEvent?.("error", { reason: `http_${resp.status}` });
      return;
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const block = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        let name = "message";
        let dataLine = "";
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) name = line.slice(6).trim();
          else if (line.startsWith("data:")) dataLine += line.slice(5).trimStart();
        }
        if (!dataLine) continue;
        let data;
        try {
          data = JSON.parse(dataLine);
        } catch {
          continue;
        }
        onEvent?.(name, data);
      }
    }
  },
};

export default api;
