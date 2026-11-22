import { useState } from "react";
import { BookOpen, Calculator, ChevronDown, FileSearch, Globe, Link2, Loader2, Newspaper, Rss, Check, Search, TrendingUp, Wrench, Map } from "lucide-react";
import type { ToolStep } from "../types";

const META: Record<string, { label: string; icon: typeof Search }> = {
  document_search: { label: "Searching your documents", icon: FileSearch },
  web_search: { label: "Searching the web", icon: Globe },
  fetch_url: { label: "Reading a webpage", icon: Link2 },
  wikipedia_search: { label: "Checking Wikipedia", icon: BookOpen },
  read_rss_feed: { label: "Reading an RSS feed", icon: Rss },
  discover_sitemap: { label: "Discovering sitemap pages", icon: Map },
  calculator: { label: "Calculating", icon: Calculator },
  stock_lookup: { label: "Looking up a stock", icon: TrendingUp },
  browser_search: { label: "Groq browser search", icon: Newspaper },
};

function summarize(step: ToolStep): string {
  try {
    const a = JSON.parse(step.arguments || "{}");
    const v = a.query ?? a.url ?? a.feed_url ?? a.site_url ?? a.expression ?? a.ticker;
    if (v) return String(v);
  } catch { /* fall through */ }
  return step.arguments === "{}" ? "" : step.arguments;
}

function StepRow({ step }: { step: ToolStep }) {
  const [open, setOpen] = useState(false);
  const meta = META[step.name] ?? { label: step.name || "Tool", icon: Wrench };
  const Icon = meta.icon;
  const running = step.status === "running";
  const detail = summarize(step);
  return (
    <li className="animate-pop">
      <button
        onClick={() => !running && setOpen((o) => !o)}
        className="group flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left text-[13px] hover:bg-slate-100 dark:hover:bg-slate-800/70"
      >
        <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-md ${running ? "bg-brand-100 text-brand-600 dark:bg-brand-600/20 dark:text-brand-400" : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"}`}>
          <Icon size={13} />
        </span>
        <span className="font-medium text-slate-700 dark:text-slate-200">{meta.label}</span>
        {detail && <span className="min-w-0 flex-1 truncate font-mono text-xs text-slate-400">{detail}</span>}
        <span className="ml-auto shrink-0 text-slate-400">
          {running ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} className="text-emerald-500" />}
        </span>
        {!running && <ChevronDown size={14} className={`shrink-0 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`} />}
      </button>
      {open && step.result_preview && (
        <pre className="mx-2 mb-1 mt-1 max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 font-mono text-xs leading-relaxed text-slate-600 dark:bg-slate-900 dark:text-slate-300">
          {step.result_preview}
        </pre>
      )}
    </li>
  );
}

export default function ToolTrace({ steps, live }: { steps: ToolStep[]; live: boolean }) {
  const [open, setOpen] = useState(true);
  if (!steps.length) return null;
  const running = steps.some((s) => s.status === "running");
  return (
    <div className="mb-3 overflow-hidden rounded-xl border border-slate-200 bg-white/60 dark:border-slate-800 dark:bg-slate-900/40">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2 px-3 py-2 text-xs font-medium text-slate-500 hover:text-slate-700 dark:hover:text-slate-300">
        {running || live ? <Loader2 size={13} className="animate-spin text-brand-500" /> : <Check size={13} className="text-emerald-500" />}
        {running ? "Working…" : `Used ${steps.length} tool call${steps.length === 1 ? "" : "s"}`}
        <ChevronDown size={14} className={`ml-auto transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <ul className="space-y-0.5 border-t border-slate-100 p-1.5 dark:border-slate-800">{steps.map((s, i) => <StepRow key={s.id ?? i} step={s} />)}</ul>}
    </div>
  );
}
