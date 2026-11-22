"""Run a small optional RAGAS evaluation. This invokes the configured LLM judge and uses Groq quota."""
from __future__ import annotations
import json
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
from rag_app.config import CHROMA_DIR, GROQ_API_KEY, GROQ_MODEL
from rag_app.retrieval import HybridRetriever
from groq import Groq

QUESTIONS_FILE = ROOT / "evaluation_questions.json"

def main():
    if not GROQ_API_KEY:
        raise SystemExit("Set GROQ_API_KEY in .env. Generation and LLM-as-judge calls consume Groq API quota.")
    if not QUESTIONS_FILE.exists():
        raise SystemExit("Create evaluation_questions.json using evaluation_questions.example.json first.")
    rows = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    if not rows or any(not row.get("ground_truth") for row in rows):
        raise SystemExit("Every evaluation row must include a non-empty ground_truth reference answer.")

    retriever = HybridRetriever(CHROMA_DIR)
    if retriever.count() == 0:
        raise SystemExit("No indexed documents. Launch app.py and index documents first.")

    # Generate answers only from the retrieved chunks so this evaluates the RAG pipeline,
    # not unrelated web/Wikipedia/stock tools selected by the agent.
    client = Groq(api_key=GROQ_API_KEY)
    questions, answers, contexts, ground_truths = [], [], [], []
    for row in rows:
        question = row["question"].strip()
        hits = retriever.search(question, k=5)
        retrieved_contexts = [hit["text"] for hit in hits]
        context_block = "\n\n---\n\n".join(retrieved_contexts) or "No relevant context was retrieved."
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "Answer only from the supplied retrieved context. If the context does not contain the answer, clearly say so. Do not use outside knowledge."},
                {"role": "user", "content": f"Question: {question}\n\nRetrieved context:\n{context_block}"},
            ],
            max_completion_tokens=1200,
            reasoning_effort="low",
        )
        questions.append(question)
        answers.append(completion.choices[0].message.content or "")
        contexts.append(retrieved_contexts)
        ground_truths.append(row["ground_truth"])

    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import context_precision, context_recall, faithfulness, answer_relevancy
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from langchain_groq import ChatGroq
    from langchain_huggingface import HuggingFaceEmbeddings

    judge_llm = LangchainLLMWrapper(ChatGroq(model=GROQ_MODEL, api_key=GROQ_API_KEY, temperature=0.1))
    judge_embeddings = LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    ))
    data = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    }
    result = evaluate(
        Dataset.from_dict(data),
        metrics=[context_precision, context_recall, faithfulness, answer_relevancy],
        llm=judge_llm,
        embeddings=judge_embeddings,
    )
    print(result)
    (ROOT / "ragas_results.txt").write_text(str(result), encoding="utf-8")

if __name__ == "__main__":
    main()
