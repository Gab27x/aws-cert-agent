"""Evaluación de RAG con Ragas.

Uso (dentro del contenedor agent):
  python eval/ragas_eval.py --input eval/sample_questions.jsonl

Input JSONL (una línea por ejemplo):
  {"question": "...", "ground_truth": "..."}

- `ground_truth` es opcional. Si no existe, se calculan métricas que no lo requieren.
- Este script llama al grafo actual (LangGraph) para obtener `answer` y `context`.

Requisitos:
- OPENAI_API_KEY configurado (Ragas usa LLM/embeddings para evaluar)
- RAG ya ingestado si quieres evaluar con contexto real
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from datasets import Dataset


# Cuando se ejecuta como archivo (`python eval/ragas_eval.py`), Python pone
# `/app/eval` en sys.path[0] y puede no incluir `/app`. Esto rompe `import agent`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _split_context(context: str, max_chunks: int) -> List[str]:
    parts = [p.strip() for p in context.split("\n\n") if p.strip()]
    if max_chunks > 0:
        return parts[:max_chunks]
    return parts


def _build_ragas_wrappers():
    """Construye LLM/Embeddings para Ragas.

    Ragas ha cambiado su API entre versiones. Este helper intenta envolver
    objetos de LangChain si los wrappers están disponibles; si no, devuelve
    los objetos base.
    """

    eval_provider = (os.getenv("RAGAS_LLM_PROVIDER") or os.getenv("LLM_PROVIDER") or "openai").lower()

    # LLM "judge" para evaluación
    if eval_provider == "groq":
        from langchain_groq import ChatGroq

        eval_llm_model = os.getenv("RAGAS_LLM_MODEL", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
        llm: Any = ChatGroq(model=eval_llm_model, temperature=0)
    else:
        from langchain_openai import ChatOpenAI

        eval_llm_model = os.getenv("RAGAS_LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
        llm = ChatOpenAI(model=eval_llm_model, temperature=0)

    # Embeddings para métricas (por ahora se mantienen en OpenAI)
    from langchain_openai import OpenAIEmbeddings

    eval_embedding_model = os.getenv(
        "RAGAS_EMBEDDING_MODEL", os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    )
    embeddings: Any = OpenAIEmbeddings(model=eval_embedding_model)

    try:
        from ragas.llms import LangchainLLMWrapper  # type: ignore

        llm = LangchainLLMWrapper(llm)
    except Exception:
        pass

    try:
        from ragas.embeddings import LangchainEmbeddingsWrapper  # type: ignore

        embeddings = LangchainEmbeddingsWrapper(embeddings)
    except Exception:
        pass

    return llm, embeddings


def _resolve_metrics(has_ground_truth: bool):
    # Métricas base (no requieren referencia)
    from ragas.metrics import answer_relevancy, faithfulness

    metrics = [answer_relevancy, faithfulness]

    if not has_ground_truth:
        return metrics

    # Métricas con referencia (nombres cambian entre versiones)
    try:
        from ragas.metrics import context_precision, context_recall

        metrics.extend([context_precision, context_recall])
        return metrics
    except Exception:
        pass

    try:
        from ragas.metrics import context_precision_with_reference, context_recall

        metrics.extend([context_precision_with_reference, context_recall])
        return metrics
    except Exception:
        pass

    # Si no existen en la versión instalada, seguimos con las base
    return metrics


def _json_safe(value: Any) -> Any:
    if callable(value):
        try:
            value = value()
        except Exception:
            return None

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    # Numpy scalars
    try:
        import numpy as np  # type: ignore

        if isinstance(value, np.generic):
            return value.item()
    except Exception:
        pass

    # Fallback
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluar tu RAG con Ragas")
    parser.add_argument(
        "--input",
        required=True,
        help="Ruta a JSONL con {question, ground_truth?}",
    )
    parser.add_argument(
        "--max-context-chunks",
        type=int,
        default=10,
        help="Máximo de chunks de contexto a pasar a Ragas (0 = sin límite)",
    )
    parser.add_argument(
        "--output-json",
        default="eval/ragas_results.json",
        help="Archivo JSON de salida con métricas agregadas",
    )
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY en el entorno (Ragas necesita LLM/embeddings para evaluar).")

    # Import tardío: solo cuando se ejecuta dentro del contenedor.
    from agent.graph import build_graph

    graph = build_graph()

    samples = _load_jsonl(args.input)
    if not samples:
        raise SystemExit("El input está vacío.")

    rows: List[Dict[str, Any]] = []
    has_ground_truth = True

    for s in samples:
        question = (s.get("question") or "").strip()
        if not question:
            continue

        ground_truth = s.get("ground_truth")
        if not ground_truth:
            has_ground_truth = False

        out = graph.invoke({"question": question, "history": []})
        answer = (out.get("answer") or "").strip()
        context_str = (out.get("context") or "").strip()

        contexts = _split_context(context_str, args.max_context_chunks) if context_str else []

        row: Dict[str, Any] = {
            "question": question,
            "answer": answer,
            "contexts": contexts,
        }
        if ground_truth:
            row["ground_truth"] = ground_truth

        rows.append(row)

    if not rows:
        raise SystemExit("No se pudieron construir filas (revisa el input).")

    dataset = Dataset.from_list(rows)

    from ragas import evaluate

    metrics = _resolve_metrics(has_ground_truth)

    llm, embeddings = _build_ragas_wrappers()

    result = evaluate(dataset, metrics=metrics, llm=llm, embeddings=embeddings)

    # Ragas >=0.2 retorna EvaluationResult con `scores` (lista de dicts, una por fila)
    scores = getattr(result, "scores", None)
    if not isinstance(scores, list):
        scores = []

    metric_names = set()
    for row_score in scores:
        if isinstance(row_score, dict):
            metric_names.update(row_score.keys())

    metrics_avg: Dict[str, Optional[float]] = {}
    for name in sorted(metric_names):
        values: List[float] = []
        for row_score in scores:
            if not isinstance(row_score, dict):
                continue
            v = row_score.get(name)
            if isinstance(v, (int, float)):
                values.append(float(v))
        metrics_avg[name] = (sum(values) / len(values)) if values else None

    payload = {
        "metrics_avg": metrics_avg,
        "scores_per_sample": scores,
        "num_samples": len(rows),
        "has_ground_truth": has_ground_truth,
        "input": args.input,
        "total_tokens": _json_safe(getattr(result, "total_tokens", None)),
        "total_cost": _json_safe(getattr(result, "total_cost", None)),
        "run_id": _json_safe(getattr(result, "run_id", None)),
    }

    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
