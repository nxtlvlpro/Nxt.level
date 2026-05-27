import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Upload,
  RefreshCw,
  FileText,
  AlertTriangle,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  X,
} from "lucide-react";
import api from "../../../lib/api";
import { BackBar, SectionHeader, EmptyHint } from "./widgets";
import { useT } from "../../../i18n/LanguageContext";

const SEVERITY_COLORS = {
  critical: "text-red-400 border-red-500/40 bg-red-500/10",
  high: "text-orange-400 border-orange-500/40 bg-orange-500/10",
  medium: "text-yellow-300 border-yellow-500/40 bg-yellow-500/10",
  low: "text-emerald-400 border-emerald-500/40 bg-emerald-500/10",
  unknown: "text-slate-400 border-slate-500/30 bg-slate-500/10",
};

const ACCEPTED = ".pdf,.docx,.txt,.md,.csv,.log";
const MAX_MB = 10;

function SeverityBadge({ severity }) {
  const cls = SEVERITY_COLORS[severity] || SEVERITY_COLORS.unknown;
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded-full border text-[9px] uppercase tracking-widest ${cls}`}
      data-testid={`severity-${severity || "unknown"}`}
    >
      {severity || "unknown"}
    </span>
  );
}

function UploadBox({ onUploaded }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState("");

  const submit = async (file) => {
    setError("");
    if (!file) return;
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`Файл больше ${MAX_MB} MB`);
      return;
    }
    setBusy(true);
    setProgress(`загружаю · ${file.name}`);
    try {
      const res = await api.documentUpload(file, { company_id: "default" });
      setProgress(`готово · severity=${res.severity || "—"}`);
      onUploaded?.(res);
    } catch (e) {
      const detail = e?.response?.data?.detail || e.message || "upload failed";
      setError(String(detail));
      setProgress("");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const onChange = (e) => {
    const f = e.target.files?.[0];
    if (f) submit(f);
  };

  const onDrop = (e) => {
    e.preventDefault();
    if (busy) return;
    const f = e.dataTransfer?.files?.[0];
    if (f) submit(f);
  };

  return (
    <div
      onDragOver={(e) => e.preventDefault()}
      onDrop={onDrop}
      className="border border-dashed border-brand-turquoise/30 bg-brand-dark/40 rounded-xl p-4 flex flex-col items-center justify-center gap-2"
      data-testid="documents-upload-zone"
    >
      <Upload className="w-5 h-5 text-brand-turquoise" />
      <div className="text-[11px] text-slate-300 text-center">
        {t("ops.docs.upload.drop", { n: MAX_MB })}
      </div>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={busy}
        className="neo-btn rounded-full px-3 py-1.5 text-brand-turquoise text-[10px] uppercase tracking-widest flex items-center gap-1.5 disabled:opacity-40"
        data-testid="documents-upload-btn"
      >
        <Upload className="w-3 h-3" />
        {busy ? t("ops.docs.upload.analyzing") : t("ops.docs.upload.choose")}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        onChange={onChange}
        className="hidden"
        data-testid="documents-file-input"
      />
      {progress && !error && (
        <div
          className="text-[10px] text-brand-turquoise/80"
          data-testid="documents-progress"
        >
          {progress}
        </div>
      )}
      {error && (
        <div
          className="text-[10px] text-red-400 border border-red-500/30 rounded px-2 py-1 max-w-full break-words"
          data-testid="documents-upload-error"
        >
          {error}
        </div>
      )}
    </div>
  );
}

function FindingRow({ finding, idx }) {
  return (
    <div
      className="border border-white/5 rounded-lg p-2.5 bg-brand-dark/30 space-y-1.5"
      data-testid={`finding-${idx}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[9px] uppercase tracking-widest text-slate-500">
          {finding.category || "other"}
        </span>
        <SeverityBadge severity={finding.severity} />
      </div>
      {finding.quote && (
        <blockquote className="text-[11px] text-slate-200 italic border-l-2 border-brand-turquoise/40 pl-2">
          “{finding.quote}”
        </blockquote>
      )}
      {finding.risk && (
        <div className="text-[11px] text-orange-300/90">
          <AlertTriangle className="w-3 h-3 inline mr-1 -mt-0.5" />
          {finding.risk}
        </div>
      )}
      {finding.recommendation && (
        <div className="text-[11px] text-emerald-300/90">
          <ShieldCheck className="w-3 h-3 inline mr-1 -mt-0.5" />
          {finding.recommendation}
        </div>
      )}
    </div>
  );
}

function DocumentCard({ doc, expanded, onToggle }) {
  const { t, lang } = useT();
  const findings = doc.findings || [];
  const actions = doc.recommended_actions || [];
  const locale = lang === "ru" ? "ru-RU" : "en-US";
  return (
    <div
      className="border border-white/5 bg-brand-dark/40 rounded-xl p-3 space-y-2"
      data-testid={`doc-card-${doc.id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <FileText className="w-3.5 h-3.5 text-brand-turquoise shrink-0" />
            <span
              className="text-[12px] text-slate-100 truncate"
              data-testid="doc-title"
            >
              {doc.title || doc.filename}
            </span>
          </div>
          <div className="text-[9px] uppercase tracking-widest text-slate-500">
            {new Date(doc.created_at).toLocaleString(locale)} ·{" "}
            {Math.round((doc.size_bytes || 0) / 1024)} kb · {doc.chunks || 0} chunks
          </div>
        </div>
        <SeverityBadge severity={doc.severity} />
      </div>

      {doc.summary && (
        <div className="text-[11px] text-slate-300 leading-relaxed">
          {doc.summary}
        </div>
      )}

      <div className="flex items-center justify-between pt-1">
        <span className="text-[9px] uppercase tracking-widest text-slate-500">
          {findings.length} findings · {actions.length} actions
        </span>
        <button
          type="button"
          onClick={onToggle}
          className="text-brand-turquoise text-[10px] uppercase tracking-widest flex items-center gap-1"
          data-testid={`doc-toggle-${doc.id}`}
        >
          {expanded ? (
            <>
              {t("ops.docs.collapse")} <ChevronUp className="w-3 h-3" />
            </>
          ) : (
            <>
              {t("ops.docs.expand")} <ChevronDown className="w-3 h-3" />
            </>
          )}
        </button>
      </div>

      {expanded && (
        <div className="space-y-2 pt-1">
          {findings.length === 0 ? (
            <div className="text-[10px] text-slate-500 italic">
              {t("ops.docs.no_risks")}
            </div>
          ) : (
            findings.map((f, i) => (
              <FindingRow key={i} finding={f} idx={i} />
            ))
          )}
          {actions.length > 0 && (
            <div className="border border-emerald-500/20 bg-emerald-500/5 rounded-lg p-2.5">
              <div className="text-[9px] uppercase tracking-widest text-emerald-400 mb-1">
                recommended actions
              </div>
              <ul className="space-y-1">
                {actions.map((a, i) => (
                  <li
                    key={i}
                    className="text-[11px] text-emerald-200/90 flex gap-1.5"
                  >
                    <span className="text-emerald-400">›</span>
                    <span>{a}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {doc.mock && (
            <div className="text-[9px] uppercase tracking-widest text-yellow-400">
              {t("ops.docs.mock_provider")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function DocumentsPanel({ onBack }) {
  const { t } = useT();
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [firstLoaded, setFirstLoaded] = useState(false);
  const [expanded, setExpanded] = useState({});

  const refresh = useCallback(async () => {
    const res = await api.documentsList(undefined, 50).catch(() => ({
      documents: [],
    }));
    setDocs(res.documents || []);
    setFirstLoaded(true);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const runRefresh = async () => {
    if (loading) return;
    setLoading(true);
    try {
      await refresh();
    } finally {
      setLoading(false);
    }
  };

  const onUploaded = (doc) => {
    setDocs((prev) => [doc, ...prev.filter((d) => d.id !== doc.id)]);
    setExpanded((prev) => ({ ...prev, [doc.id]: true }));
  };

  const stats = docs.reduce(
    (acc, d) => {
      acc.total += 1;
      const sev = d.severity || "unknown";
      acc[sev] = (acc[sev] || 0) + 1;
      return acc;
    },
    { total: 0 }
  );

  return (
    <section
      className="glass-card rounded-2xl window-border glow-turquoise-subtle p-4 space-y-3"
      data-testid="ops-documents"
    >
      <BackBar title={t("ops.docs.title")} onBack={onBack} />

      <UploadBox onUploaded={onUploaded} />

      <div className="flex items-center justify-between gap-3">
        <div className="flex-1 min-w-0">
          <SectionHeader
            title="uploaded documents"
            right={`${stats.total} files`}
          />
        </div>
        <button
          onClick={runRefresh}
          disabled={loading}
          className="neo-btn rounded-full px-3 py-1.5 text-brand-turquoise text-[10px] uppercase tracking-widest flex items-center gap-1.5 disabled:opacity-40"
          data-testid="documents-refresh"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
          refresh
        </button>
      </div>

      {stats.total > 0 && (
        <div className="grid grid-cols-4 gap-2" data-testid="documents-stats">
          {["critical", "high", "medium", "low"].map((sev) => (
            <div
              key={sev}
              className={`border rounded-lg p-2 text-center ${
                SEVERITY_COLORS[sev]
              } ${!stats[sev] ? "opacity-40" : ""}`}
            >
              <div className="text-[9px] uppercase tracking-widest opacity-80">
                {sev}
              </div>
              <div className="text-sm font-bold">{stats[sev] || 0}</div>
            </div>
          ))}
        </div>
      )}

      <div className="space-y-2">
        {firstLoaded && docs.length === 0 && (
          <EmptyHint testId="documents-empty">
            {t("ops.docs.empty")}
          </EmptyHint>
        )}
        {docs.map((d) => (
          <DocumentCard
            key={d.id}
            doc={d}
            expanded={!!expanded[d.id]}
            onToggle={() =>
              setExpanded((prev) => ({ ...prev, [d.id]: !prev[d.id] }))
            }
          />
        ))}
      </div>

      <div className="text-[10px] text-slate-500 leading-relaxed border-t border-white/5 pt-2">
        <X className="w-3 h-3 inline mr-1" />
        {t("ops.docs.footer")}
      </div>
    </section>
  );
}
