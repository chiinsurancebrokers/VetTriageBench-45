#!/usr/bin/env python3
"""
VetTriageBench-45 Comparison Report Generator
Reads multiple results JSON files and produces a head-to-head markdown report.

Usage:
    python3 compare.py /tmp/results_claude*.json /tmp/results_openai*.json /tmp/results_groq*.json
"""

import json, sys, argparse
from datetime import datetime
from pathlib import Path

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def generate(result_paths, output_path):
    results = [load(p) for p in result_paths]
    results.sort(key=lambda r: -r["triage_accuracy_pct"])

    now = datetime.now().strftime("%Y-%m-%d")
    lines = []

    lines += [
        "# VetTriageBench-45 — Multi-Model Comparison Report",
        f"\n**Generated:** {now}  ",
        f"**Vignettes:** 45 standardised veterinary cases (dogs + cats)  ",
        f"**Models compared:** {len(results)}  ",
        "\n---\n",
        "## Head-to-Head Results\n",
        "| Rank | Model | Provider | Accuracy | Safe overtriage | ⚠️ Unsafe undertriage |",
        "|---|---|---|---|---|---|",
    ]

    medals = ["🥇","🥈","🥉"] + ["  "] * 10
    for i, r in enumerate(results):
        unsafe_cell = (f"**{r['unsafe_undertriage_pct']}%** ❌"
                       if r["unsafe_undertriage_pct"] > 0
                       else f"{r['unsafe_undertriage_pct']}% ✅")
        lines.append(
            f"| {medals[i]} {i+1} | `{r['model']}` | {r['provider']} | "
            f"**{r['triage_accuracy_pct']}%** ({r['n_exact']}/{r['n_vignettes']}) | "
            f"{r['overtriage_pct']}% | {unsafe_cell} |"
        )

    lines += [
        "\n---\n",
        "## Per-Category Accuracy\n",
        "| Model | EMERGENCY | URGENT | SELF_CARE |",
        "|---|---|---|---|",
    ]
    for r in results:
        cats = r.get("per_category", {})
        def cat_str(cat):
            s = cats.get(cat, {})
            return f"{s.get('accuracy_pct','?')}% ({s.get('exact','?')}/{s.get('n','?')})"
        lines.append(
            f"| `{r['model']}` | {cat_str('EMERGENCY')} | {cat_str('URGENT')} | {cat_str('SELF_CARE')} |"
        )

    # Key insight
    winner = results[0]
    safest = min(results, key=lambda r: r["unsafe_undertriage_pct"])
    lines += [
        "\n---\n",
        "## Key Findings\n",
    ]
    lines.append(f"- **Highest accuracy:** `{winner['model']}` at {winner['triage_accuracy_pct']}%")
    lines.append(f"- **Lowest unsafe undertriage:** `{safest['model']}` at {safest['unsafe_undertriage_pct']}%")

    all_zero_unsafe = all(r["unsafe_undertriage_pct"] == 0 for r in results)
    if all_zero_unsafe:
        lines.append("- ✅ **All models achieved 0% unsafe undertriage** — no emergency case was downgraded")
    else:
        unsafe_models = [r["model"] for r in results if r["unsafe_undertriage_pct"] > 0]
        lines.append(f"- ⚠️ Models with unsafe undertriage: {', '.join(f'`{m}`' for m in unsafe_models)}")

    # Overtriage note
    lines += [
        "",
        "> **Note on overtriage:** Safe overtriage (classifying URGENT as EMERGENCY,",
        "> or SELF_CARE as URGENT) is conservative and acceptable in a safety-critical",
        "> context — it means the system errs on the side of caution. Only **unsafe",
        "> undertriage** (missing a genuine emergency) is penalised in this benchmark.",
        "",
        "---\n",
        "## Comparison with Human Symptom-Checker Benchmarks\n",
        "| System | Accuracy | Unsafe undertriage | Source |",
        "|---|---|---|---|",
        "| Median of 23 commercial apps | ~57% | Not reported | Semigran et al., BMJ 2015 |",
        "| Isabel Healthcare | ~84% | — | Semigran et al., BMJ 2015 |",
        "| CareRoute (adaptive) | 88.9% | 0% | medRxiv preprint, Aug 2025 |",
    ]
    for r in results:
        unsafe_note = "✅ 0%" if r["unsafe_undertriage_pct"]==0 else f"⚠️ {r['unsafe_undertriage_pct']}%"
        lines.append(
            f"| **`{r['model']}`** (VetTriageBench-45) | **{r['triage_accuracy_pct']}%** "
            f"| {unsafe_note} | This study |"
        )
    lines += [
        "",
        "> ⚠️ Direct comparison with human benchmarks is illustrative only.",
        "> VetTriageBench-45 uses veterinary vignettes (dogs+cats), not the",
        "> Semigran-45 human vignettes. Methodology follows the same framework.",
        "",
        "---\n",
        "## Methodology\n",
        "- **45 vignettes**: 15 EMERGENCY / 15 URGENT / 15 SELF_CARE",
        "- **Species**: Dogs (25) and Cats (20)",
        "- **Triage framework**: Veterinary Triage List (Ruys et al. 2012) / VetTriS (Groesser et al. 2025)",
        "- **Scoring**: Exact match = correct; Safe overtriage = acceptable (0 pts); Unsafe undertriage = safety failure (−1 pt)",
        "- **System prompt**: Identical across all models for fair comparison",
        "- **Self-administered**: Not independently peer-reviewed. n=45 (95% CI ~±8–9pp).",
        "",
        "---\n",
        "## Run Details\n",
        "| Model | Provider | Run date |",
        "|---|---|---|",
    ]
    for r in results:
        rd = r.get("run_date","")[:10]
        lines.append(f"| `{r['model']}` | {r['provider']} | {rd} |")

    report = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Comparison report → {output_path}")
    return report


def main():
    p = argparse.ArgumentParser(description="VetTriageBench-45 Comparison Report")
    p.add_argument("results", nargs="+", help="Results JSON files")
    p.add_argument("--output", "-o", default="/tmp/vettriagbench45_comparison.md")
    args = p.parse_args()

    missing = [f for f in args.results if not Path(f).exists()]
    if missing:
        print(f"ERROR: Files not found: {missing}")
        sys.exit(1)

    generate(args.results, args.output)
    print(f"\nView with: cat {args.output}")


if __name__ == "__main__":
    main()
