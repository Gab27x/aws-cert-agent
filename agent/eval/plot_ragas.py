"""Genera gráficas PNG a partir de `eval/ragas_results.json`.

Uso (dentro del contenedor agent):
  python eval/plot_ragas.py

Salida:
  - eval/ragas_metrics_avg.png
  - eval/ragas_metrics_boxplot.png

Nota:
  Requiere `matplotlib` (ya incluido en requirements.txt).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def main() -> int:
    results_path = Path("eval/ragas_results.json")
    if not results_path.exists():
        raise SystemExit(
            "No existe eval/ragas_results.json. Primero corre: "
            "python eval/ragas_eval.py --input eval/sample_questions.jsonl"
        )

    with results_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    metrics_avg = data.get("metrics_avg") or {}
    scores_per_sample = data.get("scores_per_sample") or []

    # Import tardío para que el script falle con un mensaje claro si falta.
    try:
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        raise SystemExit(
            "Falta matplotlib dentro del contenedor. Rebuild: docker compose build agent"
        ) from e

    # ── 1) Promedios por métrica (barh) ─────────────────────────
    if metrics_avg:
        avg = pd.Series(metrics_avg, dtype="float64").sort_values()

        plt.figure(figsize=(8, max(3, 0.6 * len(avg))))
        ax = avg.plot(kind="barh")
        ax.set_title("Ragas — Métricas promedio")
        ax.set_xlabel("Score (0 a 1)")
        ax.set_xlim(0, 1)
        plt.tight_layout()
        plt.savefig("eval/ragas_metrics_avg.png", dpi=160)
        plt.close()
    else:
        print("WARN: metrics_avg vacío; no genero ragas_metrics_avg.png")

    # ── 2) Distribución por muestra (boxplot) ───────────────────
    if scores_per_sample:
        df = pd.DataFrame(scores_per_sample)
        # Mantener orden estable de columnas
        df = df.reindex(sorted(df.columns), axis=1)

        plt.figure(figsize=(8, 4))
        ax = df.plot(kind="box")
        ax.set_title("Ragas — Distribución por pregunta")
        ax.set_ylabel("Score (0 a 1)")
        ax.set_ylim(0, 1)
        plt.tight_layout()
        plt.savefig("eval/ragas_metrics_boxplot.png", dpi=160)
        plt.close()
    else:
        print("WARN: scores_per_sample vacío; no genero ragas_metrics_boxplot.png")

    print("OK -> eval/ragas_metrics_avg.png")
    print("OK -> eval/ragas_metrics_boxplot.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
