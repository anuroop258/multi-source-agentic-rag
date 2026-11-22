import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Menu, Moon, Sun, X } from "lucide-react";
import { api, streamChat } from "./api";
import type { AppStatus, ChatMessage, ConversationSummary, DocInfo, Settings, StreamEvent, ToolStep } from "./types";
import Sidebar from "./components/Sidebar";
import MessageView from "./components/MessageView";
import Composer from "./components/Composer";
import EmptyState from "./components/EmptyState";
import SettingsMenu from "./components/SettingsMenu";

const uid = () => crypto.randomUUID().replace(/-/g, "");
const load = <T,>(key: string, fallback: T): T => {
  try { const v = localStorage.getItem(key); return v ? (JSON.parse(v) as T) : fallback; } catch { return fallback; }
};

export default function App() {
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [docs, setDocs] = useState<DocInfo[]>([]);
  const [activeId, setActiveId] = useState<string | null>(() => localStorage.getItem("activeId"));
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  const [settings, setSettings] = useState<Settings>(() => load<Settings>("settings", { searchProvider: "duckduckgo", browserSearch: false }));
  const [serverDown, setServerDown] = useState(false);

  const abort = useRef<AbortController | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);

  const refreshStatus = useCallback(() => api.status().then((s) => { setStatus(s); setServerDown(false); }).catch(() => setServerDown(true)), []);
  const refreshDocs = useCallback(() => { api.documents().then(setDocs).catch(() => {}); refreshStatus(); }, [refreshStatus]);
  const refreshConversations = useCallback(() => api.conversations().then(setConversations).catch(() => {}), []);

  useEffect(() => {
    refreshStatus().then(() => {});
    refreshDocs();
    refreshConversations();
  }, [refreshStatus, refreshDocs, refreshConversations]);

  // Apply the server's defaults once, unless the user already chose something.
  useEffect(() => {
    if (status && !localStorage.getItem("settings")) {
      setSettings({ searchProvider: status.search.default_provider, browserSearch: status.search.browser_search_default });
    }
  }, [status]);
  useEffect(() => { localStorage.setItem("settings", JSON.stringify(settings)); }, [settings]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  // Load history for the active conversation.
  useEffect(() => {
    if (!activeId) { setMessages([]); return; }
    localStorage.setItem("activeId", activeId);
    if (busy) return; // never clobber a live stream
    api.conversation(activeId)
      .then((c) => setMessages(c.messages.map((m) => ({ id: String(m.id), role: m.role, content: m.content, trace: m.trace?.map((t) => ({ ...t, status: "done" as const })) }))))
      .catch(() => setMessages([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId]);

  useEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const patchLast = (fn: (m: ChatMessage) => ChatMessage) =>
    setMessages((ms) => (ms.length ? [...ms.slice(0, -1), fn(ms[ms.length - 1])] : ms));

  const onEvent = (e: StreamEvent) => {
    if (e.type === "tool_start") {
      patchLast((m) => ({ ...m, trace: [...(m.trace ?? []), ...e.calls.map((c): ToolStep => ({ ...c, status: "running" }))] }));
    } else if (e.type === "tool_done") {
      const { type: _t, ...step } = e;
      patchLast((m) => {
        const trace = [...(m.trace ?? [])];
        const i = trace.findIndex((s) => s.status === "running" && (step.id ? s.id === step.id : s.name === step.name));
        const done: ToolStep = { ...step, status: "done" };
        if (i >= 0) trace[i] = { ...trace[i], ...done }; else trace.push(done);
        return { ...m, trace };
      });
    } else if (e.type === "answer") {
      patchLast((m) => ({ ...m, content: e.answer, pending: false, trace: e.tool_trace.map((t) => ({ ...t, status: "done" as const })) }));
    } else if (e.type === "error") {
      patchLast((m) => ({ ...m, content: e.message, error: true, pending: false, trace: m.trace?.map((t) => ({ ...t, status: "done" as const })) }));
    }
  };

  const send = async (text: string) => {
    if (busy) return;
    const id = activeId ?? uid();
    if (!activeId) setActiveId(id);
    stick.current = true;
    setMessages((ms) => [
      ...ms,
      { id: uid(), role: "user", content: text },
      { id: uid(), role: "assistant", content: "", trace: [], pending: true },
    ]);
    setBusy(true);
    const ctl = new AbortController();
    abort.current = ctl;
    try {
      await streamChat({ conversation_id: id, message: text, settings }, onEvent, ctl.signal);
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        patchLast((m) => ({ ...m, pending: false, content: m.content || "_Stopped._", trace: m.trace?.map((t) => ({ ...t, status: "done" as const })) }));
      } else {
        onEvent({ type: "error", message: err instanceof Error ? err.message : String(err) });
      }
    } finally {
      setBusy(false);
      abort.current = null;
      patchLast((m) => (m.pending ? { ...m, pending: false } : m));
      refreshConversations();
    }
  };

  const newChat = () => { if (busy) return; setActiveId(null); localStorage.removeItem("activeId"); setMessages([]); setDrawer(false); };
  const select = (id: string) => { if (busy || id === activeId) { setDrawer(false); return; } setActiveId(id); setDrawer(false); };
  const remove = async (id: string) => {
    await api.deleteConversation(id);
    if (id === activeId) newChat();
    refreshConversations();
  };

  const sidebar = (
    <Sidebar conversations={conversations} activeId={activeId} docs={docs} status={status}
      onSelect={select} onNew={newChat} onDelete={remove} onDocsChanged={refreshDocs} />
  );

  const needsKey = status && !status.groq_configured;

  return (
    <div className="flex h-full">
      {/* desktop sidebar */}
      <aside className="hidden w-72 shrink-0 border-r border-slate-200 dark:border-slate-800 md:block">{sidebar}</aside>
      {/* mobile drawer */}
      {drawer && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setDrawer(false)} />
          <aside className="absolute inset-y-0 left-0 w-[85%] max-w-xs shadow-2xl">
            <button onClick={() => setDrawer(false)} className="absolute right-2 top-3 z-10 rounded p-1 text-slate-400"><X size={18} /></button>
            {sidebar}
          </aside>
        </div>
      )}

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-slate-200/70 px-3 dark:border-slate-800">
          <button onClick={() => setDrawer(true)} className="grid h-9 w-9 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 md:hidden"><Menu size={18} /></button>
          <div className="min-w-0 flex-1 truncate text-sm font-medium text-slate-600 dark:text-slate-300">
            {conversations.find((c) => c.id === activeId)?.title ?? "New chat"}
          </div>
          <SettingsMenu settings={settings} status={status} onChange={setSettings} />
          <button onClick={() => setDark((d) => !d)} title="Toggle theme" className="grid h-9 w-9 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
            {dark ? <Sun size={17} /> : <Moon size={17} />}
          </button>
        </header>

        {(serverDown || needsKey || status?.retrieval_error) && (
          <div className="flex items-start gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            <span>
              {serverDown ? "Can't reach the cloud API. Check the Cloudflare Pages deployment and D1 binding."
                : needsKey ? "GROQ_API_KEY is missing from Cloudflare Pages secrets. Add it in Pages Settings → Variables and Secrets, then redeploy."
                : `Cloud retrieval setup failed: ${status?.retrieval_error}`}
            </span>
          </div>
        )}

        <div
          ref={scroller}
          onScroll={(e) => { const el = e.currentTarget; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; }}
          className="min-h-0 flex-1 overflow-y-auto"
        >
          {messages.length === 0 ? (
            <EmptyState ready={!busy && !!status?.groq_configured} onPick={send} />
          ) : (
            <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
              {messages.map((m) => <MessageView key={m.id} m={m} />)}
            </div>
          )}
        </div>

        <Composer busy={busy} disabled={!status?.groq_configured} onSend={send} onStop={() => abort.current?.abort()} />
      </main>
    </div>
  );
}
