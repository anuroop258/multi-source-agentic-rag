import { useRef, useState } from "react";
import { FileText, Loader2, Trash2, UploadCloud, X } from "lucide-react";
import type { DocInfo } from "../types";
import { api } from "../api";

const fmt = (n: number | null) => (n == null ? "" : n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`);

interface Props { docs: DocInfo[]; chunks: number; onChanged: () => void }

export default function KnowledgeBase({ docs, chunks, onChanged }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState<{ ok: boolean; text: string }[]>([]);

  const upload = async (files: FileList | File[]) => {
    const list = Array.from(files);
    if (!list.length) return;
    setBusy(true); setNotes([]);
    try {
      const r = await api.upload(list);
      setNotes([
        ...r.indexed.map((d) => ({ ok: true, text: `${d.name}: ${d.chunks ? `${d.chunks} chunks` : "upload accepted"} (${d.status ?? "indexing"})` })),
        ...r.rejected.map((d) => ({ ok: false, text: `${d.name}: ${d.reason}` })),
      ]);
      onChanged();
    } catch (e) {
      setNotes([{ ok: false, text: e instanceof Error ? e.message : String(e) }]);
    } finally { setBusy(false); }
  };

  const remove = async (name: string) => { await api.deleteDocument(name); onChanged(); };
  const clear = async () => {
    if (!confirm("Clear the whole document index? Cloudflare AI Search files will be deleted.")) return;
    await api.clearIndex(); onChanged();
  };

  return (
    <div>
      <div className="mb-2 flex items-center justify-between px-1">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Knowledge base</h2>
        {chunks > 0 && <button onClick={clear} className="text-[11px] text-slate-400 hover:text-red-500">Clear index</button>}
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}
        onClick={() => !busy && input.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-4 text-center transition ${drag ? "border-brand-500 bg-brand-50 dark:bg-brand-600/10" : "border-slate-300 hover:border-brand-400 dark:border-slate-700"}`}
      >
        <input ref={input} type="file" hidden multiple accept=".pdf,.docx,.txt,.md,.markdown,.rst,.csv" onChange={(e) => { if (e.target.files) upload(e.target.files); e.target.value = ""; }} />
        {busy ? (
          <div className="flex flex-col items-center gap-1 text-xs text-slate-500">
            <Loader2 size={20} className="animate-spin text-brand-500" />Uploading and indexing in the cloud…
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1 text-xs text-slate-500">
            <UploadCloud size={20} className="text-slate-400" />
            <span><b className="text-slate-700 dark:text-slate-200">Drop files</b> or click</span>
            <span className="text-[11px] text-slate-400">PDF · DOCX · TXT · MD · RST · CSV (max 4 MB each)</span>
          </div>
        )}
      </div>

      {notes.length > 0 && (
        <ul className="mt-2 space-y-1">
          {notes.map((n, i) => (
            <li key={i} className={`flex items-start gap-1.5 rounded-md px-2 py-1 text-[11px] ${n.ok ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300" : "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300"}`}>
              <span className="min-w-0 flex-1 break-words">{n.text}</span>
              <button onClick={() => setNotes((x) => x.filter((_, j) => j !== i))}><X size={12} /></button>
            </li>
          ))}
        </ul>
      )}

      {docs.length > 0 && (
        <ul className="mt-2 space-y-0.5">
          {docs.map((d) => (
            <li key={d.name} className="group flex items-center gap-2 rounded-lg px-2 py-1.5 text-[13px] hover:bg-slate-100 dark:hover:bg-slate-800/70">
              <FileText size={15} className={d.indexed ? "text-brand-500" : "text-slate-400"} />
              <div className="min-w-0 flex-1">
                <div className="truncate" title={d.name}>{d.name}</div>
                <div className="text-[11px] text-slate-400">{d.indexed ? `${d.chunks} chunks` : (d.index_status || "not indexed")}{d.size != null && ` · ${fmt(d.size)}`}</div>
              </div>
              <button onClick={() => remove(d.name)} title="Delete" className="hidden rounded p-1 text-slate-400 hover:text-red-500 group-hover:block"><Trash2 size={14} /></button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
