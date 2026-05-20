import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const http = axios.create({
  baseURL: API,
  timeout: 180000,
  headers: { "Content-Type": "application/json" },
});

export const api = {
  health: () => http.get("/health").then((r) => r.data),
  seed: () => http.post("/seed").then((r) => r.data),

  chat: (payload) => http.post("/chat", payload).then((r) => r.data),
  recentRequests: (limit = 10) =>
    http.get(`/requests?limit=${limit}`).then((r) => r.data),

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
};

export default api;
