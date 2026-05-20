import React, { useEffect, useState } from "react";
import { Network, Activity, Wrench, Radar, Bot, FileText } from "lucide-react";
import api from "../../lib/api";
import { WidgetCard } from "./ops/widgets";
import CrossDeptPanel from "./ops/CrossDeptPanel";
import DiagnosticsPanel from "./ops/DiagnosticsPanel";
import SkillsPanel from "./ops/SkillsPanel";
import MarketPanel from "./ops/MarketPanel";
import HermesPanel from "./ops/HermesPanel";
import DocumentsPanel from "./ops/DocumentsPanel";

function CrossDeptWidget({ data, onOpen }) {
  const tasks = data?.tasks || [];
  const multi = tasks.filter((t) => t.multi_department).length;
  const last = tasks[0];
  return (
    <WidgetCard
      title="cross-dept · coordinator"
      onOpen={onOpen}
      testId="widget-crossdept"
      status={`${tasks.length} tasks`}
    >
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-brand-turquoise/10 border border-brand-turquoise/30 flex items-center justify-center">
          <Network className="w-5 h-5 text-brand-turquoise" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-slate-200 text-[12px] truncate">
            {last?.query || "пока нет координаций"}
          </div>
          <div className="text-[9px] uppercase tracking-widest text-slate-500 mt-0.5">
            {multi} multi-dept · {tasks.length - multi} single
          </div>
        </div>
      </div>
    </WidgetCard>
  );
}

function DiagnosticsWidget({ data, onOpen }) {
  const conf = data?.summary?.avg_confidence;
  const esc = data?.summary?.escalation_rate;
  const contras = data?.contradictions ?? 0;
  const alertish = (esc != null && esc > 0.2) || contras > 0;
  return (
    <WidgetCard
      title="diagnostics · self-audit"
      onOpen={onOpen}
      testId="widget-diagnostics"
      accent={alertish ? "text-orange-400" : "text-brand-turquoise"}
      status={alertish ? "attention" : "stable"}
    >
      <div className="flex items-center gap-3">
        <div
          className={`w-10 h-10 rounded-xl border flex items-center justify-center ${
            alertish
              ? "bg-orange-500/10 border-orange-500/30"
              : "bg-brand-turquoise/10 border-brand-turquoise/30"
          }`}
        >
          <Activity
            className={`w-5 h-5 ${
              alertish ? "text-orange-400" : "text-brand-turquoise"
            }`}
          />
        </div>
        <div className="grid grid-cols-3 gap-2 flex-1 text-center">
          <div>
            <div className="text-[9px] text-slate-500 uppercase">conf</div>
            <div className="text-brand-turquoise text-sm font-bold">
              {conf == null ? "—" : `${(conf * 100).toFixed(0)}%`}
            </div>
          </div>
          <div>
            <div className="text-[9px] text-slate-500 uppercase">esc</div>
            <div className="text-orange-400 text-sm font-bold">
              {esc == null ? "—" : `${(esc * 100).toFixed(0)}%`}
            </div>
          </div>
          <div>
            <div className="text-[9px] text-slate-500 uppercase">contra</div>
            <div className="text-red-400 text-sm font-bold">{contras}</div>
          </div>
        </div>
      </div>
    </WidgetCard>
  );
}

function SkillsWidget({ data, onOpen }) {
  const skills = data?.skills || [];
  const enabled = skills.filter((s) => s.enabled).length;
  const auto = skills.filter((s) => s.auto_generated).length;
  const top = skills.slice().sort((a, b) => b.hit_count - a.hit_count)[0];
  return (
    <WidgetCard
      title="skills · creator"
      onOpen={onOpen}
      testId="widget-skills"
      status={`${enabled}/${skills.length}`}
    >
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
          <Wrench className="w-5 h-5 text-emerald-400" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-slate-200 text-[12px] truncate">
            {top ? `top: ${top.name}` : "навыков ещё нет"}
          </div>
          <div className="text-[9px] uppercase tracking-widest text-slate-500 mt-0.5">
            {auto} auto · {skills.length - auto} manual
          </div>
        </div>
      </div>
    </WidgetCard>
  );
}

function MarketWidget({ data, onOpen }) {
  const signals = data?.signals || [];
  const digest = data?.digest;
  return (
    <WidgetCard
      title="market · radar"
      onOpen={onOpen}
      testId="widget-market"
      status={`${signals.length} signals`}
    >
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center">
          <Radar className="w-5 h-5 text-purple-400" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-slate-200 text-[12px] truncate">
            {digest?.digest
              ? digest.digest.split("\n")[0].slice(0, 80)
              : signals[0]?.headline || "нет сигналов"}
          </div>
          <div className="text-[9px] uppercase tracking-widest text-slate-500 mt-0.5">
            {digest
              ? `digest ${new Date(digest.created_at).toLocaleDateString(
                  "ru-RU"
                )}`
              : "ожидание скана"}
          </div>
        </div>
      </div>
    </WidgetCard>
  );
}

function HermesWidget({ data, onOpen }) {  const status = data?.health?.status || "offline";
  const jobs = data?.jobs || [];
  const online = status === "online";
  return (
    <WidgetCard
      title="hermes · agent"
      onOpen={onOpen}
      testId="widget-hermes"
      accent={online ? "text-purple-400" : "text-slate-500"}
      status={online ? "online" : status}
    >
      <div className="flex items-center gap-3">
        <div
          className={`w-10 h-10 rounded-xl border flex items-center justify-center ${
            online
              ? "bg-purple-500/10 border-purple-500/30"
              : "bg-slate-500/10 border-slate-500/30"
          }`}
        >
          <Bot
            className={`w-5 h-5 ${online ? "text-purple-400" : "text-slate-500"}`}
          />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-slate-200 text-[12px] truncate">
            {online
              ? `${jobs.length} активных заданий`
              : "gateway не запущен (порт 8642)"}
          </div>
          <div className="text-[9px] uppercase tracking-widest text-slate-500 mt-0.5">
            NousResearch · OpenAI-compatible
          </div>
        </div>
      </div>
    </WidgetCard>
  );
}

function DocumentsWidget({ data, onOpen }) {
  const docs = data?.documents || [];
  const last = docs[0];
  const critical = docs.filter(
    (d) => d.severity === "critical" || d.severity === "high"
  ).length;
  const alertish = critical > 0;
  return (
    <WidgetCard
      title="documents · compliance"
      onOpen={onOpen}
      testId="widget-documents"
      accent={alertish ? "text-orange-400" : "text-brand-turquoise"}
      status={`${docs.length} files`}
    >
      <div className="flex items-center gap-3">
        <div
          className={`w-10 h-10 rounded-xl border flex items-center justify-center ${
            alertish
              ? "bg-orange-500/10 border-orange-500/30"
              : "bg-brand-turquoise/10 border-brand-turquoise/30"
          }`}
        >
          <FileText
            className={`w-5 h-5 ${
              alertish ? "text-orange-400" : "text-brand-turquoise"
            }`}
          />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-slate-200 text-[12px] truncate">
            {last ? last.title || last.filename : "загрузите первый документ"}
          </div>
          <div className="text-[9px] uppercase tracking-widest text-slate-500 mt-0.5">
            {critical} risk · {docs.length - critical} ok
          </div>
        </div>
      </div>
    </WidgetCard>
  );
}

export default function OpsView() {
  const [sub, setSub] = useState(null);
  const [data, setData] = useState({
    crossDept: null,
    diagnostics: null,
    skills: null,
    market: null,
    hermes: null,
    documents: null,
  });

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      const [
        cd,
        summary,
        contras,
        skills,
        signals,
        digests,
        hHealth,
        hJobs,
        docs,
      ] = await Promise.all([
        api.crossDeptTasks(10).catch(() => ({ tasks: [] })),
        api.diagnosticsSummary(200).catch(() => null),
        api.diagnosticsList(30).catch(() => ({ contradictions: [] })),
        api.skillsList(false, 50).catch(() => ({ skills: [] })),
        api.marketSignals(undefined, 20).catch(() => ({ signals: [] })),
        api.marketDigests(1).catch(() => ({ digests: [] })),
        api.hermesHealth().catch(() => null),
        api.hermesJobsList().catch(() => ({ jobs: [] })),
        api.documentsList(undefined, 20).catch(() => ({ documents: [] })),
      ]);
      if (!mounted) return;
      setData({
        crossDept: { tasks: cd.tasks || [] },
        diagnostics: {
          summary,
          contradictions: (contras.contradictions || []).length,
        },
        skills: { skills: skills.skills || [] },
        market: {
          signals: signals.signals || [],
          digest: (digests.digests || [])[0] || null,
        },
        hermes: {
          health: hHealth,
          jobs: hJobs.jobs || [],
        },
        documents: { documents: docs.documents || [] },
      });
    };
    load();
    const t = setInterval(load, 30000);
    return () => {
      mounted = false;
      clearInterval(t);
    };
  }, []);

  if (sub === "cross-dept")
    return <CrossDeptPanel onBack={() => setSub(null)} />;
  if (sub === "diagnostics")
    return <DiagnosticsPanel onBack={() => setSub(null)} />;
  if (sub === "skills") return <SkillsPanel onBack={() => setSub(null)} />;
  if (sub === "market") return <MarketPanel onBack={() => setSub(null)} />;
  if (sub === "hermes") return <HermesPanel onBack={() => setSub(null)} />;
  if (sub === "documents")
    return <DocumentsPanel onBack={() => setSub(null)} />;

  return (
    <div className="space-y-3" data-testid="ops-view">
      <div className="flex justify-between items-center px-1">
        <span className="text-brand-turquoise font-light text-xs">
          ops.cockpit
        </span>
        <span className="text-slate-500 text-[10px] uppercase tracking-widest animate-flicker">
          live · 6 modules
        </span>
      </div>
      <div className="space-y-3 lg:space-y-0 lg:grid lg:grid-cols-2 lg:gap-4">
        <CrossDeptWidget
          data={data.crossDept}
          onOpen={() => setSub("cross-dept")}
        />
        <DiagnosticsWidget
          data={data.diagnostics}
          onOpen={() => setSub("diagnostics")}
        />
        <SkillsWidget data={data.skills} onOpen={() => setSub("skills")} />
        <MarketWidget data={data.market} onOpen={() => setSub("market")} />
        <HermesWidget data={data.hermes} onOpen={() => setSub("hermes")} />
        <DocumentsWidget
          data={data.documents}
          onOpen={() => setSub("documents")}
        />
      </div>
    </div>
  );
}
