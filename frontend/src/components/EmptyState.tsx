import { Calculator, FileSearch, Globe, Link2, Sparkles } from "lucide-react";

const IDEAS = [
  { icon: FileSearch, title: "Ask your documents", text: "Summarize the key points of my uploaded files", hint: "Upload files in the sidebar first" },
  { icon: Globe, title: "Research the web", text: "What are the latest developments in open-source LLMs this week?" },
  { icon: Link2, title: "Read a page", text: "Read https://en.wikipedia.org/wiki/Retrieval-augmented_generation and explain it simply" },
  { icon: Calculator, title: "Exact maths", text: "What is (1249 * 37 + 18.5) / 4 ?" },
];

export default function EmptyState({ onPick, ready }: { onPick: (t: string) => void; ready: boolean }) {
  return (
    <div className="mx-auto flex min-h-full max-w-3xl flex-col items-center justify-center px-4 py-10 text-center">
      <div className="mb-5 grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-violet-600 text-white shadow-lg shadow-brand-500/30">
        <Sparkles size={26} />
      </div>
      <h1 className="text-2xl font-semibold tracking-tight">What do you want to find out?</h1>
      <p className="mt-2 max-w-md text-sm text-slate-500">
        An agent that picks the right source for you — your documents, the live web, Wikipedia, feeds, or a calculator — and shows its work.
      </p>
      <div className="mt-8 grid w-full gap-3 sm:grid-cols-2">
        {IDEAS.map(({ icon: Icon, title, text, hint }) => (
          <button
            key={title}
            disabled={!ready}
            onClick={() => onPick(text)}
            className="group rounded-xl border border-slate-200 bg-white p-4 text-left transition hover:-translate-y-0.5 hover:border-brand-400 hover:shadow-md disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-brand-500"
          >
            <div className="mb-2 flex items-center gap-2 text-sm font-medium"><Icon size={16} className="text-brand-500" />{title}</div>
            <div className="text-[13px] leading-snug text-slate-500">{text}</div>
            {hint && <div className="mt-1.5 text-[11px] text-slate-400">{hint}</div>}
          </button>
        ))}
      </div>
    </div>
  );
}
