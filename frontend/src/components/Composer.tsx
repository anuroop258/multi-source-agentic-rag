import { useEffect, useRef, useState } from "react";
import { ArrowUp, Square } from "lucide-react";

interface Props {
  busy: boolean;
  disabled?: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}

export default function Composer({ busy, disabled, onSend, onStop }: Props) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [text]);

  useEffect(() => { if (!busy) ref.current?.focus(); }, [busy]);

  const submit = () => {
    const t = text.trim();
    if (!t || busy || disabled) return;
    onSend(t);
    setText("");
  };

  return (
    <div className="border-t border-slate-200/70 bg-white/80 px-4 pb-4 pt-3 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
      <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-slate-300 bg-white p-2 shadow-sm focus-within:border-brand-500 focus-within:ring-4 focus-within:ring-brand-500/10 dark:border-slate-700 dark:bg-slate-900">
        <textarea
          ref={ref}
          rows={1}
          value={text}
          autoFocus
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); }
          }}
          placeholder="Ask about your documents, search the web, read a URL, calculate…"
          className="max-h-[200px] min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-[0.95rem] outline-none placeholder:text-slate-400"
        />
        {busy ? (
          <button onClick={onStop} title="Stop" className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-slate-900 text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900">
            <Square size={14} fill="currentColor" />
          </button>
        ) : (
          <button onClick={submit} disabled={!text.trim() || disabled} title="Send" className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-600 text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-40">
            <ArrowUp size={18} />
          </button>
        )}
      </div>
      <p className="mx-auto mt-2 max-w-3xl text-center text-[11px] text-slate-400">Enter to send · Shift+Enter for a new line · Answers can be wrong — check the cited sources.</p>
    </div>
  );
}
