import React, { useCallback, useEffect, useState } from "react";
import { RefreshCw, Power } from "lucide-react";
import api from "../../../lib/api";
import { BackBar, SectionHeader, EmptyHint } from "./widgets";
import { useT } from "../../../i18n/LanguageContext";

function SkillRow({ skill, onToggle }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className={`border rounded-xl p-3 transition-colors ${
        skill.enabled
          ? "border-brand-turquoise/30 bg-brand-turquoise/5"
          : "border-white/5 bg-brand-dark/40 opacity-60"
      }`}
      data-testid={`skill-row-${skill.id}`}
    >
      <div className="flex justify-between items-start gap-2">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="min-w-0 flex-1 text-left"
        >
          <div className="text-slate-200 text-[12px] truncate font-medium">
            {skill.name}
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[9px] uppercase tracking-widest text-brand-turquoise">
              {skill.intent}
            </span>
            <span className="text-[9px] text-slate-500">
              hits {skill.hit_count} · conf{" "}
              {Math.round((skill.last_confidence_avg || 0) * 100)}%
            </span>
            {skill.auto_generated && (
              <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400">
                auto
              </span>
            )}
          </div>
        </button>
        <button
          onClick={() => onToggle(skill)}
          className={`p-1.5 rounded-lg neo-btn ${
            skill.enabled ? "text-brand-turquoise" : "text-slate-500"
          }`}
          data-testid={`skill-toggle-${skill.id}`}
          aria-label="toggle"
        >
          <Power className="w-3.5 h-3.5" />
        </button>
      </div>
      {expanded && (
        <div className="mt-2 pt-2 border-t border-white/5 space-y-1.5">
          <div className="text-[9px] uppercase text-slate-500">terms</div>
          <div className="flex flex-wrap gap-1">
            {(skill.signature_terms || []).map((t) => (
              <span
                key={t}
                className="text-[10px] px-1.5 py-0.5 rounded bg-brand-dark/60 text-slate-300"
              >
                {t}
              </span>
            ))}
          </div>
          <div className="text-[9px] uppercase text-slate-500 mt-1">
            template
          </div>
          <div className="text-[11px] text-slate-300 whitespace-pre-wrap">
            {skill.prompt_template}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SkillsPanel({ onBack }) {
  const { t } = useT();
  const [skills, setSkills] = useState([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(
    () =>
      api
        .skillsList(false, 100)
        .then((d) => setSkills(d.skills || []))
        .catch(() => {}),
    []
  );

  useEffect(() => {
    refresh();
  }, [refresh]);

  const runScan = async () => {
    if (loading) return;
    setLoading(true);
    try {
      await api.skillsScan();
      await refresh();
    } finally {
      setLoading(false);
    }
  };

  const toggleSkill = async (skill) => {
    try {
      await api.skillsToggle(skill.id, !skill.enabled);
      setSkills((arr) =>
        arr.map((s) =>
          s.id === skill.id ? { ...s, enabled: !skill.enabled } : s
        )
      );
    } catch (err) {
      if (process.env.NODE_ENV !== "production") {
        // eslint-disable-next-line no-console
        console.error("SkillsPanel: toggle failed", err);
      }
    }
  };

  const auto = skills.filter((s) => s.auto_generated).length;
  const enabled = skills.filter((s) => s.enabled).length;

  return (
    <section
      className="glass-card rounded-2xl window-border glow-turquoise-subtle p-4 space-y-3"
      data-testid="ops-skills"
    >
      <BackBar title={t("ops.skills.title")} onBack={onBack} />

      <div className="flex justify-between items-center">
        <div className="flex gap-3 text-[10px] uppercase tracking-widest">
          <span className="text-brand-turquoise">{enabled} enabled</span>
          <span className="text-slate-500">·</span>
          <span className="text-emerald-400">{auto} auto</span>
          <span className="text-slate-500">·</span>
          <span className="text-slate-400">{skills.length} total</span>
        </div>
        <button
          onClick={runScan}
          disabled={loading}
          className="neo-btn rounded-full px-3 py-1.5 text-brand-turquoise text-[10px] uppercase tracking-widest flex items-center gap-1.5 disabled:opacity-40"
          data-testid="skills-scan"
        >
          <RefreshCw
            className={`w-3 h-3 ${loading ? "animate-spin" : ""}`}
          />
          {loading ? t("ops.skills.scanning") : t("ops.skills.discover")}
        </button>
      </div>

      <SectionHeader title={t("ops.skills.registered")} />
      <div className="space-y-2">
        {skills.length === 0 && (
          <EmptyHint testId="skills-empty">
            {t("ops.skills.empty.hint")}
          </EmptyHint>
        )}
        {skills.map((s) => (
          <SkillRow key={s.id} skill={s} onToggle={toggleSkill} />
        ))}
      </div>
    </section>
  );
}
