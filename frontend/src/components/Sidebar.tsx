import { MessageSquare, Plus, Sparkles, Trash2 } from "lucide-react";
import type { AppStatus, ConversationSummary, DocInfo } from "../types";
import KnowledgeBase from "./KnowledgeBase";

interface Props {
  conversations: ConversationSummary[];
  activeId: string | null;
  docs: DocInfo[];
  status: AppStatus | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onDocsChanged: () => void;
}

export default function Sidebar({ conversations, activeId, docs, status, onSelect, onNew, onDelete, onDocsChanged }: Props) {
  return (
    <div className="flex h-full w-full flex-col bg-slate-50 dark:bg-slate-900/60">
      <div className="flex items-center gap-2.5 px-4 pb-3 pt-4">
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-brand-500 to-violet-600 text-white"><Sparkles size={16} /></div>
        <div className="leading-tight">
          <div className="text-sm font-semibold">Agentic RAG</div>
          <div className="text-[11px] text-slate-400">Multi-source research</div>
        </div>
      </div>

      <div className="px-3">
        <button onClick={onNew} className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-brand-700">
          <Plus size={16} /> New chat
        </button>
      </div>

      <div className="mt-4 min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        <h2 className="mb-1 px-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Recent</h2>
        {conversations.length === 0 ? (
          <p className="px-1 py-2 text-xs text-slate-400">No conversations yet.</p>
        ) : (
          <ul className="space-y-0.5">
            {conversations.map((c) => (
              <li key={c.id} className="group relative">
                <button
                  onClick={() => onSelect(c.id)}
                  className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[13px] ${c.id === activeId ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-600/15 dark:text-brand-100" : "hover:bg-slate-100 dark:hover:bg-slate-800/70"}`}
                >
                  <MessageSquare size={14} className="shrink-0 opacity-60" />
                  <span className="truncate pr-5">{c.title}</span>
                </button>
                <button
                  onClick={() => { if (confirm("Delete this conversation?")) onDelete(c.id); }}
                  title="Delete"
                  className="absolute right-1.5 top-1/2 hidden -translate-y-1/2 rounded p-1 text-slate-400 hover:text-red-500 group-hover:block"
                >
                  <Trash2 size={14} />
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-6"><KnowledgeBase docs={docs} chunks={status?.indexed_chunks ?? 0} onChanged={onDocsChanged} /></div>
      </div>

      <div className="border-t border-slate-200 px-4 py-3 text-[11px] text-slate-400 dark:border-slate-800">
        <div className="flex items-center gap-1.5"><span className={`h-1.5 w-1.5 rounded-full ${status?.groq_configured ? "bg-emerald-500" : "bg-amber-500"}`} />{status ? (status.groq_configured ? "Groq connected" : "Groq key missing") : "Connecting…"}</div>
        <div className="mt-0.5 truncate font-mono" title={status?.model}>{status?.model}</div>
        <div className="mt-0.5">{status?.indexed_chunks ?? 0} chunks indexed · stored locally</div>
      </div>
    </div>
  );
}
