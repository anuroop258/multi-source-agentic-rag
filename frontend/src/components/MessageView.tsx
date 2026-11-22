import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, Check, Copy, Sparkles } from "lucide-react";
import type { ChatMessage } from "../types";
import ToolTrace from "./ToolTrace";

export default function MessageView({ m }: { m: ChatMessage }) {
  const [copied, setCopied] = useState(false);

  if (m.role === "user") {
    return (
      <div className="flex justify-end animate-pop">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-brand-600 px-4 py-2.5 text-[0.95rem] leading-relaxed text-white shadow-sm">
          {m.content}
        </div>
      </div>
    );
  }

  const copy = async () => {
    await navigator.clipboard.writeText(m.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex gap-3 animate-pop">
      <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-brand-500 to-violet-600 text-white shadow-sm">
        <Sparkles size={16} />
      </div>
      <div className="min-w-0 flex-1">
        <ToolTrace steps={m.trace ?? []} live={!!m.pending} />
        {m.pending && !m.content ? (
          <div className="dots py-2 text-slate-500"><span /><span /><span /></div>
        ) : m.error ? (
          <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            <span className="break-words">{m.content}</span>
          </div>
        ) : (
          <>
            <div className="md"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: (p) => <a {...p} target="_blank" rel="noreferrer noopener" /> }}>{m.content}</ReactMarkdown></div>
            <div className="mt-2 flex">
              <button onClick={copy} className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300">
                {copied ? <><Check size={13} /> Copied</> : <><Copy size={13} /> Copy</>}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
