import { useEffect, useRef, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import type { AppStatus, Settings } from "../types";

interface Props { settings: Settings; status: AppStatus | null; onChange: (s: Settings) => void }

export default function SettingsMenu({ settings, status, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const tavily = status?.search.tavily_available ?? false;

  return (
    <div ref={box} className="relative">
      <button onClick={() => setOpen((o) => !o)} title="Web research settings" className="grid h-9 w-9 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
        <SlidersHorizontal size={17} />
      </button>
      {open && (
        <div className="absolute right-0 top-11 z-30 w-80 rounded-xl border border-slate-200 bg-white p-4 shadow-xl dark:border-slate-700 dark:bg-slate-900">
          <h3 className="mb-3 text-sm font-semibold">Web research</h3>

          <label className="mb-1 block text-xs font-medium text-slate-500">Search provider</label>
          <select
            value={settings.searchProvider}
            onChange={(e) => onChange({ ...settings, searchProvider: e.target.value as Settings["searchProvider"] })}
            className="w-full rounded-lg border border-slate-300 bg-transparent px-2.5 py-2 text-sm outline-none focus:border-brand-500 dark:border-slate-700"
          >
            <option value="duckduckgo">DuckDuckGo (no API key)</option>
            <option value="tavily" disabled={!tavily}>Tavily {tavily ? "(API key set)" : "(no API key in .env)"}</option>
          </select>
          <p className="mt-1.5 text-[11px] leading-snug text-slate-400">Tavily is only called when selected here. Check your account's credits and billing first.</p>

          <label className="mt-4 flex cursor-pointer items-start gap-2.5">
            <input type="checkbox" className="mt-0.5 h-4 w-4 accent-brand-600" checked={settings.browserSearch} onChange={(e) => onChange({ ...settings, browserSearch: e.target.checked })} />
            <span>
              <span className="block text-sm font-medium">Groq built-in browser search</span>
              <span className="block text-[11px] leading-snug text-slate-400">Off by default. Check Groq pricing and account terms before enabling.</span>
            </span>
          </label>
        </div>
      )}
    </div>
  );
}
