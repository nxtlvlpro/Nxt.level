import React, { useEffect, useRef, useState } from "react";
import {
  Activity,
  Play,
  Loader2,
  CheckCircle2,
  XCircle,
  Eye,
  Brain,
  ShieldCheck,
  GitFork,
  Compass,
  Cpu,
  Radar,
  Lightbulb,
  Sparkles,
  Rocket,
  RefreshCw,
  Network,
  BookOpen,
} from "lucide-react";
import api from "../../lib/api";

// Canonical 10-node order — matches backend hermes_os_graph.NODE_ORDER.
// Each node carries a short label, an icon, and a colour family for the
// indicator dot. Keep this list in sync with NODE_ORDER on backend.
const NODES = [
  { id: "observation",             label: "Observe",     icon: Eye,         hint: "scan facts" },
  { id: "context_assembly",        label: "Context",     icon: Compass,     hint: "build memory" },
  { id: "constitution_validation", label: "Validate",    icon: ShieldCheck, hint: "policy check" },
  { id: "reasoning",               label: "Reason",      icon: Brain,       hint: "analyse" },
  { id: "agent_routing",           label: "Route",       icon: GitFork,     hint: "pick owner" },
  { id: "execution",               label: "Execute",     icon: Cpu,         hint: "act" },
  { id: "monitoring",              label: "Monitor",     icon: Radar,       hint: "watch KPIs" },
  { id: "learning",                label: "Learn",       icon: Lightbulb,   hint: "extract lesson" },
  { id: "improvement",             label: "Improve",     icon: Sparkles,    hint: "find gaps" },
  { id: "evolution",               label: "Evolve",      icon: Rocket,      hint: "self-evolve" },
];

const PRESET_EVENTS = [
  {
    id: "new_client_msg",
    label: "New client message",
    payload: {
      source: "channel_webhook",
      kind: "new_client_message",
      lang: "ru",
      user_id: "demo_client",
      company_id: "nxt8_demo",
      payload: {
        text: "Здравствуйте, нужен пилот по ИИ для отдела продаж. Бюджет ~1 млн руб.",
        channel: "telegram",
        session_id: "os_demo",
      },
    },
  },
  {
    id: "doc_upload",
    label: "Contract uploaded",
    payload: {
      source: "document_upload",
      kind: "contract_review",
      lang: "ru",
      user_id: "ops_manager",
      company_id: "nxt8_demo",
      payload: { filename: "contract_v3.pdf", risk_hint: "liability clause unusual" },
    },
  },
  {
    id: "task_created",
    label: "Task created",
    payload: {
      source: "task_created",
      kind: "internal_task",
      lang: "ru",
      user_id: "lead_engineer",
      company_id: "nxt8_demo",
      payload: { title: "Quarterly compliance audit", priority: "high" },
    },
  },
];

function statusBadge(status) {
  if (status === "running") {
    return (
      <span className="inline-flex items-center gap-1.5 text-brand-turquoise">
        <Loader2 className="w-3 h-3 animate-spin" /> running
      </span>
    );
  }
  if (status === "done") {
    return (
      <span className="inline-flex items-center gap-1.5 text-emerald-400">
        <CheckCircle2 className="w-3 h-3" /> done
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="inline-flex items-center gap-1.5 text-red-400">
        <XCircle className="w-3 h-3" /> error
      </span>
    );
  }
  return <span className="text-slate-500">idle</span>;
}

const NodeCard = React.forwardRef(function NodeCard(
  { node, state, slice, isActive },
  ref
) {
  const Icon = node.icon;
  const border =
    state === "active"
      ? "border-brand-turquoise/60 shadow-[0_0_18px_var(--brand-turquoise)]"
      : state === "done"
        ? "border-emerald-500/40"
        : state === "error"
          ? "border-red-500/40"
          : "border-white/10";
  const tint =
    state === "active"
      ? "text-brand-turquoise"
      : state === "done"
        ? "text-emerald-400"
        : state === "error"
          ? "text-red-400"
          : "text-slate-500";
  return (
    <div
      ref={ref}
      className={`relative rounded-xl border ${border} bg-brand-dark/60 backdrop-blur-md p-3 transition-all ${
        isActive ? "scale-[1.02]" : ""
      }`}
      data-testid={`os-node-${node.id}`}
      data-state={state}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center bg-white/5 ${tint}`}>
          <Icon className="w-4 h-4" strokeWidth={1.7} />
        </div>
        <div className="min-w-0">
          <div className={`text-[11px] uppercase tracking-widest ${tint}`}>{node.label}</div>
          <div className="text-[9px] text-slate-500">{node.hint}</div>
        </div>
        {state === "active" && (
          <Loader2 className="w-3 h-3 animate-spin text-brand-turquoise ml-auto" />
        )}
        {state === "done" && (
          <CheckCircle2 className="w-3 h-3 text-emerald-400 ml-auto" />
        )}
        {state === "error" && (
          <XCircle className="w-3 h-3 text-red-400 ml-auto" />
        )}
      </div>
      {slice && (
        <div
          className="text-[10.5px] text-slate-400 leading-relaxed line-clamp-3 break-words"
          title={typeof slice === "string" ? slice : JSON.stringify(slice)}
        >
          {slice}
        </div>
      )}
    </div>
  );
});

function extractSliceText(nodeId, slice) {
  if (!slice || typeof slice !== "object") return "";
  switch (nodeId) {
    case "observation":
      return slice.summary || "";
    case "context_assembly":
      if (slice.totals) {
        const t = slice.totals;
        return `stm=${t.stm_cycles ?? 0} ops=${t.ops_records ?? 0} kg=${t.kg_edges ?? 0} inst=${t.inst_lessons ?? 0}`;
      }
      return "";
    case "constitution_validation":
      return `${(slice.status || "").toUpperCase()} — ${slice.reason || ""}`;
    case "reasoning":
      return slice.goal || slice.problem || "";
    case "agent_routing":
      return `${(slice.mode || "").toUpperCase()}${
        slice.assignees && slice.assignees.length ? ` → ${slice.assignees.join(", ")}` : ""
      }`;
    case "execution":
      return slice.action || `${slice.mode || ""} (${slice.status || ""})`;
    case "monitoring":
      return `KPIs: ${(slice.kpis || []).slice(0, 3).join(", ") || "—"}`;
    case "learning":
      return `${slice.saved_inst ?? 0} lessons, ${slice.saved_kg ?? 0} KG edges`;
    case "improvement":
      return `${slice.saved_count ?? 0} recommendation(s)`;
    case "evolution":
      return slice.self_assessment || "";
    default:
      return "";
  }
}

function RecentCyclesPanel({ cycles, onPick }) {
  if (!cycles.length) {
    return (
      <div className="text-[11px] text-slate-500 italic px-1">
        No cycles yet. Trigger one above to see it appear here.
      </div>
    );
  }
  return (
    <ul className="space-y-1.5">
      {cycles.map((c) => (
        <li key={c.cycle_id}>
          <button
            onClick={() => onPick(c)}
            className="w-full text-left rounded-md border border-white/5 hover:border-brand-turquoise/40 bg-white/[0.02] hover:bg-brand-turquoise/[0.04] px-2.5 py-1.5 transition-colors"
            data-testid={`os-cycle-${c.cycle_id}`}
          >
            <div className="text-[10.5px] text-slate-300 flex items-center gap-1.5">
              <span className="font-mono">{c.cycle_id.slice(0, 8)}</span>
              <span className="text-slate-500">·</span>
              <span className="uppercase tracking-widest text-[9px] text-brand-turquoise">
                {c.event?.kind || "—"}
              </span>
              <span className="ml-auto text-slate-500 text-[9px]">{c.hops} hops</span>
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">
              {c.event?.source || "manual"} · {new Date(c.started_at).toLocaleTimeString()}
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}

function KGPanel({ edges }) {
  if (!edges.length) {
    return (
      <div className="text-[11px] text-slate-500 italic px-1">
        Knowledge graph is empty. Run a few cycles to see entity links appear.
      </div>
    );
  }
  return (
    <ul className="space-y-1">
      {edges.slice(0, 30).map((e) => (
        <li
          key={e.id || `${e.source}-${e.target}-${e.relation}`}
          className="text-[11px] flex items-center gap-1.5 px-2 py-1 rounded-md bg-white/[0.02] border border-white/5"
        >
          <span className="text-slate-300 truncate max-w-[120px]">{e.source}</span>
          <span className="text-brand-turquoise text-[9px] uppercase tracking-widest">
            {e.relation}
          </span>
          <span className="text-slate-300 truncate max-w-[140px] ml-auto">{e.target}</span>
        </li>
      ))}
    </ul>
  );
}

function InstPanel({ lessons }) {
  if (!lessons.length) {
    return (
      <div className="text-[11px] text-slate-500 italic px-1">
        No institutional memory yet. The Learning node will fill this up.
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {lessons.map((l) => (
        <li
          key={l.id}
          className="rounded-md border border-white/5 bg-white/[0.02] px-2.5 py-1.5"
        >
          <div className="flex items-center gap-1.5 mb-0.5">
            <span className="text-[9px] uppercase tracking-widest text-brand-turquoise">
              {l.scope || "process"}
            </span>
            {l.tags?.slice(0, 3).map((tag) => (
              <span
                key={tag}
                className="text-[9px] text-slate-400 bg-white/5 rounded px-1.5"
              >
                {tag}
              </span>
            ))}
          </div>
          <div className="text-[11px] text-slate-300 leading-relaxed">{l.text}</div>
        </li>
      ))}
    </ul>
  );
}

export default function HermesOSView() {
  const [preset, setPreset] = useState(PRESET_EVENTS[0].id);
  const [running, setRunning] = useState(false);
  const [nodeState, setNodeState] = useState({}); // id → "idle"|"active"|"done"|"error"
  const [nodeSlice, setNodeSlice] = useState({}); // id → extracted summary text
  const [activeNode, setActiveNode] = useState(null);
  const [cycleId, setCycleId] = useState("");
  const [finalSummary, setFinalSummary] = useState(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("cycles");
  const [cycles, setCycles] = useState([]);
  const [kgEdges, setKgEdges] = useState([]);
  const [lessons, setLessons] = useState([]);
  const [stats, setStats] = useState(null);
  const inflightRef = useRef(false);
  // Node refs for SVG connector positioning. Index matches NODES[i].
  const nodeRefs = useRef(NODES.map(() => React.createRef()));
  const gridRef = useRef(null);
  const [connectors, setConnectors] = useState([]); // [{x1,y1,x2,y2}]

  // Recompute connector geometry from node bounding rects, relative to
  // the grid container so the SVG aligns with the cards across viewport
  // sizes and CSS-grid wraps (5 cols xl → 3 md → 2 sm).
  const recomputeConnectors = () => {
    const grid = gridRef.current;
    if (!grid) return;
    const gridRect = grid.getBoundingClientRect();
    const pts = nodeRefs.current.map((r) => {
      const el = r?.current;
      if (!el) return null;
      const b = el.getBoundingClientRect();
      return {
        cx: b.left + b.width / 2 - gridRect.left,
        cy: b.top + b.height / 2 - gridRect.top,
        w:  b.width,
        h:  b.height,
        l:  b.left - gridRect.left,
        r:  b.right - gridRect.left,
        t:  b.top - gridRect.top,
        bo: b.bottom - gridRect.top,
      };
    });
    const edges = [];
    for (let i = 0; i < pts.length - 1; i += 1) {
      const a = pts[i];
      const b = pts[i + 1];
      if (!a || !b) continue;
      // Same row → exit right of A, enter left of B.
      // Wrap row    → exit bottom of A, enter top of B.
      const sameRow = Math.abs(a.cy - b.cy) < 8;
      if (sameRow) {
        edges.push({ x1: a.r, y1: a.cy, x2: b.l, y2: b.cy });
      } else {
        edges.push({ x1: a.cx, y1: a.bo, x2: b.cx, y2: b.t });
      }
    }
    setConnectors(edges);
  };

  useEffect(() => {
    recomputeConnectors();
    // Recompute on resize.
    const onResize = () => recomputeConnectors();
    window.addEventListener("resize", onResize);
    // Also on font/icon load timing — schedule a second pass.
    const tid = setTimeout(recomputeConnectors, 200);
    return () => {
      window.removeEventListener("resize", onResize);
      clearTimeout(tid);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Cards scale slightly when active — recompute when state changes so
  // the lines hug the cards perfectly even during the animation.
  useEffect(() => {
    recomputeConnectors();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodeState, activeNode]);

  const refreshAll = async () => {
    try {
      const [c, kg, inst, st] = await Promise.all([
        api.hermesOsCycles(20).catch(() => ({ items: [] })),
        api.hermesOsMemoryKG(null, 50).catch(() => ({ edges: [] })),
        api.hermesOsMemoryInst(30).catch(() => ({ lessons: [] })),
        api.hermesOsMemoryStats().catch(() => null),
      ]);
      setCycles(c.items || []);
      setKgEdges(kg.edges || []);
      setLessons(inst.lessons || []);
      setStats(st);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    refreshAll();
  }, []);

  const runCycle = async () => {
    if (inflightRef.current) return;
    inflightRef.current = true;
    setRunning(true);
    setError("");
    setNodeState({});
    setNodeSlice({});
    setActiveNode(null);
    setFinalSummary(null);
    setCycleId("");
    const payload = PRESET_EVENTS.find((p) => p.id === preset)?.payload || PRESET_EVENTS[0].payload;
    try {
      await api.hermesOsStream(payload, (name, data) => {
        if (name === "start") {
          setCycleId(data.cycle_id || "");
          return;
        }
        if (name === "error") {
          setError(data.reason || "stream error");
          return;
        }
        if (name === "done") {
          setActiveNode(null);
          setFinalSummary(data);
          // Mark any nodes that were running as done.
          setNodeState((prev) => {
            const next = { ...prev };
            NODES.forEach((n) => {
              if (next[n.id] === "active") next[n.id] = "done";
            });
            return next;
          });
          return;
        }
        // Node-tick event
        setActiveNode(name);
        setCycleId(data.cycle_id || "");
        setNodeState((prev) => {
          const next = { ...prev };
          // mark prior nodes done
          for (const n of NODES) {
            if (n.id === name) {
              next[n.id] = "active";
              break;
            }
            if (next[n.id] !== "done") next[n.id] = "done";
          }
          return next;
        });
        const text = extractSliceText(name, data.slice);
        if (text) {
          setNodeSlice((prev) => ({ ...prev, [name]: text }));
        }
      });
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      inflightRef.current = false;
      setRunning(false);
      // Refresh side panels (cycles + KG + institutional grow after a run).
      refreshAll();
    }
  };

  return (
    <div
      className="h-full overflow-y-auto pt-2 pb-12 px-4 lg:px-8 space-y-6"
      data-testid="hermes-os-view"
    >
      <header className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <div className="text-[10px] uppercase tracking-[0.3em] text-brand-turquoise mb-1.5 flex items-center gap-2">
            <Activity className="w-3 h-3" /> Hermes Operating Architecture
          </div>
          <h1 className="text-xl lg:text-2xl font-light text-slate-100">
            10-node continuous cycle
          </h1>
          <p className="text-[11px] text-slate-500 mt-1 max-w-2xl">
            Observe → Context → Validate → Reason → Route → Execute → Monitor → Learn → Improve → Evolve.
            Each business event triggers one full pass. Watch it live below.
          </p>
        </div>
        <button
          type="button"
          onClick={refreshAll}
          className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-slate-400 hover:text-brand-turquoise transition-colors"
          data-testid="os-refresh"
        >
          <RefreshCw className="w-3.5 h-3.5" /> refresh
        </button>
      </header>

      {/* Trigger row */}
      <section className="glass-card window-border glow-turquoise-subtle rounded-2xl p-4">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-[10px] uppercase tracking-widest text-slate-500">
            Trigger
          </span>
          <div
            className="inline-flex rounded-full border border-white/10 bg-brand-dark/60 p-1"
            data-testid="os-presets"
          >
            {PRESET_EVENTS.map((p) => (
              <button
                key={p.id}
                onClick={() => setPreset(p.id)}
                disabled={running}
                className={`px-3 py-1.5 rounded-full text-[10px] uppercase tracking-widest transition-colors disabled:opacity-50 ${
                  preset === p.id
                    ? "bg-brand-turquoise/15 text-brand-turquoise"
                    : "text-slate-500 hover:text-slate-300"
                }`}
                data-testid={`os-preset-${p.id}`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={runCycle}
            disabled={running}
            className="neo-btn rounded-full px-4 py-2 text-brand-turquoise text-[11px] uppercase tracking-widest flex items-center gap-1.5 disabled:opacity-50"
            data-testid="os-run-cycle"
          >
            {running ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5" />
            )}
            {running ? "Running" : "Run live"}
          </button>
          <div className="ml-auto flex items-center gap-3 text-[10px] text-slate-500">
            {cycleId && (
              <span className="font-mono">cycle {cycleId.slice(0, 8)}</span>
            )}
            {running ? (
              statusBadge("running")
            ) : finalSummary ? (
              finalSummary.error ? statusBadge("error") : statusBadge("done")
            ) : (
              statusBadge("idle")
            )}
          </div>
        </div>
        {error && (
          <div className="mt-2 text-[10px] text-red-400 border border-red-500/30 bg-red-500/5 rounded-lg px-2 py-1">
            {error}
          </div>
        )}
      </section>

      {/* 10-node graph with connector lines */}
      <section className="relative" data-testid="os-node-grid">
        {/* SVG connector overlay — drawn behind cards via z-index */}
        <svg
          className="absolute inset-0 pointer-events-none z-0"
          width="100%"
          height="100%"
          aria-hidden="true"
        >
          <defs>
            <marker
              id="os-arrow-idle"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="5"
              markerHeight="5"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(148,163,184,0.35)" />
            </marker>
            <marker
              id="os-arrow-done"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="5"
              markerHeight="5"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(52,211,153,0.7)" />
            </marker>
            <marker
              id="os-arrow-active"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--brand-turquoise)" />
            </marker>
          </defs>
          {connectors.map((e, i) => {
            const fromState = nodeState[NODES[i].id] || "idle";
            const toState = nodeState[NODES[i + 1].id] || "idle";
            // Edge classification:
            // - active: target node is currently active (=transition in flight)
            // - done:   both endpoints completed
            // - idle:   anything else
            let edgeKind = "idle";
            if (toState === "active") edgeKind = "active";
            else if (fromState === "done" && toState === "done") edgeKind = "done";
            const stroke =
              edgeKind === "active"
                ? "var(--brand-turquoise)"
                : edgeKind === "done"
                  ? "rgba(52,211,153,0.55)"
                  : "rgba(148,163,184,0.22)";
            const width = edgeKind === "active" ? 2 : 1;
            const dash = edgeKind === "active" ? "6 4" : edgeKind === "done" ? "0" : "3 3";
            const marker =
              edgeKind === "active"
                ? "url(#os-arrow-active)"
                : edgeKind === "done"
                  ? "url(#os-arrow-done)"
                  : "url(#os-arrow-idle)";
            return (
              <line
                key={i}
                x1={e.x1}
                y1={e.y1}
                x2={e.x2}
                y2={e.y2}
                stroke={stroke}
                strokeWidth={width}
                strokeDasharray={dash}
                markerEnd={marker}
                style={
                  edgeKind === "active"
                    ? {
                        filter: "drop-shadow(0 0 4px var(--brand-turquoise))",
                        animation: "os-dash-flow 0.8s linear infinite",
                      }
                    : undefined
                }
                data-testid={`os-edge-${NODES[i].id}-${NODES[i + 1].id}`}
                data-kind={edgeKind}
              />
            );
          })}
        </svg>

        <div
          ref={gridRef}
          className="relative z-10 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3"
        >
          {NODES.map((n, i) => (
            <NodeCard
              key={n.id}
              ref={nodeRefs.current[i]}
              node={n}
              state={nodeState[n.id] || "idle"}
              slice={nodeSlice[n.id] || ""}
              isActive={activeNode === n.id}
            />
          ))}
        </div>
      </section>

      {/* Memory stats strip */}
      {stats && (
        <section
          className="grid grid-cols-2 md:grid-cols-4 gap-3"
          data-testid="os-memory-stats"
        >
          <StatPill label="Short-Term" value={stats.short_term?.items ?? 0} suffix="items" />
          <StatPill
            label="Operational"
            value={stats.operational?.cycles_persisted ?? 0}
            suffix="cycles"
          />
          <StatPill
            label="Knowledge Graph"
            value={stats.knowledge_graph?.edges_total ?? 0}
            suffix="edges"
          />
          <StatPill
            label="Institutional"
            value={stats.institutional?.lessons_total ?? 0}
            suffix="lessons"
          />
        </section>
      )}

      {/* Side panels */}
      <section className="glass-card window-border rounded-2xl p-4">
        <div className="flex items-center gap-2 mb-3 border-b border-white/5 pb-2">
          <TabBtn id="cycles" active={tab} setActive={setTab} icon={Activity} label="Recent cycles" />
          <TabBtn id="kg" active={tab} setActive={setTab} icon={Network} label="Knowledge graph" />
          <TabBtn id="inst" active={tab} setActive={setTab} icon={BookOpen} label="Institutional memory" />
        </div>
        <div className="min-h-[160px] max-h-[420px] overflow-y-auto pr-1">
          {tab === "cycles" && <RecentCyclesPanel cycles={cycles} onPick={() => {}} />}
          {tab === "kg" && <KGPanel edges={kgEdges} />}
          {tab === "inst" && <InstPanel lessons={lessons} />}
        </div>
      </section>
    </div>
  );
}

function StatPill({ label, value, suffix }) {
  return (
    <div className="rounded-xl border border-white/10 bg-brand-dark/60 px-3 py-2.5">
      <div className="text-[9px] uppercase tracking-widest text-slate-500 mb-0.5">
        {label}
      </div>
      <div className="text-base text-slate-100 font-light flex items-baseline gap-1.5">
        {value}
        <span className="text-[10px] text-slate-500">{suffix}</span>
      </div>
    </div>
  );
}

function TabBtn({ id, active, setActive, icon: Icon, label }) {
  const isActive = active === id;
  return (
    <button
      type="button"
      onClick={() => setActive(id)}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] uppercase tracking-widest transition-colors ${
        isActive
          ? "bg-brand-turquoise/15 text-brand-turquoise"
          : "text-slate-500 hover:text-slate-300"
      }`}
      data-testid={`os-tab-${id}`}
    >
      <Icon className="w-3 h-3" /> {label}
    </button>
  );
}
