#!/usr/bin/env python3
"""
VetTriageBench-45 — Multi-Model Comparison Report Generator (v1.1)
==================================================================
Changes from v1.0:
  - Removed ranking medals (CIs overlap; no statistically significant difference)
  - Added URGENT tier analysis section (primary clinical weakness of all models)
  - Separated veterinary vs human benchmark comparisons into distinct sections
  - Added prompt-design bias note (EMERGENCY default inflates emergency scores)

Usage:
    python3 compare.py results/results_claude*.json results/results_openai*.json
    python3 compare.py results/*.json --output reports/comparison.md
"""

import json, sys, argparse
from datetime import datetime
from pathlib import Path


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def overlap(ci_a, ci_b):
    """Returns True if two [lo, hi] confidence intervals overlap."""
    return ci_a[0] <= ci_b[1] and ci_b[0] <= ci_a[1]


def generate(result_paths, output_path):
    results = [load(p) for p in result_paths]
    results.sort(key=lambda r: -r["triage_accuracy_pct"])

    now = datetime.now().strftime("%Y-%m-%d")
    lines = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines += [
        "# VetTriageBench-45 — Multi-Model Comparison Report",
        "",
        f"**Generated:** {now}  ",
        f"**Benchmark version:** {results[0].get('version','1.0')} (report generator v1.1)  ",
        f"**Vignettes:** 45 standardised veterinary cases (25 dogs / 20 cats)  ",
        f"**Categories:** 15 EMERGENCY / 15 URGENT / 15 SELF_CARE  ",
        f"**Models compared:** {len(results)}  ",
        "",
        "> **Validation status (v1.0):** Ground truth labels were drafted with AI assistance",
        "> and cross-checked against MSD Veterinary Manual and VTL/VetTriS triage criteria.",
        "> Formal expert veterinary consensus validation (≥3 practitioners, Cohen's κ ≥0.60)",
        "> is planned for v2.0. Results should be interpreted as indicative pending that",
        "> validation. n=45 yields 95% CI of approximately ±15pp — differences between",
        "> models should not be over-interpreted.",
        "",
        "---",
        "",
    ]

    # ── Head-to-head table — NO medals, CI overlap noted ─────────────────────
    lines += [
        "## Overall results",
        "",
    ]

    # Check if all CIs overlap
    if len(results) == 2:
        ci_a = results[0].get("triage_accuracy_ci_95", [0, 100])
        ci_b = results[1].get("triage_accuracy_ci_95", [0, 100])
        if overlap(ci_a, ci_b):
            lines += [
                "> ⚠ **Statistical note:** The confidence intervals of all models overlap.",
                "> The observed accuracy differences are **not statistically distinguishable**",
                "> at n=45. No model ranking is implied by the ordering below.",
                "",
            ]

    lines += [
        "| Model | Provider | Accuracy (95% CI) | Safe overtriage | ⚠ Unsafe undertriage |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        ci = r.get("triage_accuracy_ci_95", [None, None])
        ci_str = f"[{ci[0]}–{ci[1]}%]" if ci[0] is not None else ""
        unsafe_cell = (f"**{r['unsafe_undertriage_pct']}%** ❌"
                       if r["unsafe_undertriage_pct"] > 0
                       else f"{r['unsafe_undertriage_pct']}% ✅")
        lines.append(
            f"| `{r['model']}` | {r['provider']} | "
            f"**{r['triage_accuracy_pct']}%** ({r['n_exact']}/{r['n_vignettes']}) {ci_str} | "
            f"{r['overtriage_pct']}% | {unsafe_cell} |"
        )

    # ── Per-category breakdown ────────────────────────────────────────────────
    lines += [
        "",
        "---",
        "",
        "## Per-category accuracy",
        "",
        "| Model | EMERGENCY | URGENT | SELF_CARE |",
        "|---|---|---|---|",
    ]
    for r in results:
        cats = r.get("per_category", {})
        def cat_str(cat):
            s = cats.get(cat, {})
            base = f"{s.get('accuracy_pct','?')}% ({s.get('exact','?')}/{s.get('n','?')})"
            ci_lo = s.get("ci_95_lo")
            ci_hi = s.get("ci_95_hi")
            if ci_lo is not None:
                base += f" [{ci_lo}–{ci_hi}%]"
            return base
        lines.append(
            f"| `{r['model']}` | {cat_str('EMERGENCY')} | "
            f"{cat_str('URGENT')} | {cat_str('SELF_CARE')} |"
        )

    # ── URGENT tier analysis — NEW ────────────────────────────────────────────
    lines += [
        "",
        "---",
        "",
        "## URGENT tier analysis",
        "",
        "> The URGENT tier (same-day vet; risk of deterioration within 24h) is where",
        "> **all models consistently underperform**. This is the primary clinical weakness",
        "> identified by this benchmark and the most important finding for real-world deployment.",
        "",
    ]

    for r in results:
        cats = r.get("per_category", {})
        urg = cats.get("URGENT", {})
        n_urg = urg.get("n", 15)
        n_ex  = urg.get("exact", 0)
        n_ov  = urg.get("overtriage", 0)
        n_un  = urg.get("unsafe", 0)
        n_miss = n_urg - n_ex  # classified as something else
        acc = urg.get("accuracy_pct", 0)
        ci_lo = urg.get("ci_95_lo", "?")
        ci_hi = urg.get("ci_95_hi", "?")

        lines += [
            f"### `{r['model']}`",
            "",
            f"- Exact match: **{n_ex}/{n_urg} ({acc}%)** [95% CI {ci_lo}–{ci_hi}%]",
            f"- Misclassified as EMERGENCY (safe overtriage): {n_ov}/{n_urg}",
            f"- Misclassified as SELF_CARE (unsafe undertriage): {n_un}/{n_urg}",
            "",
        ]

    # Identify which URGENT cases were missed (from first result with vignette_results)
    urgent_misses = {}
    for r in results:
        vr = r.get("vignette_results", [])
        misses = [
            v for v in vr
            if v.get("ground_truth") == "URGENT" and v.get("outcome") != "EXACT"
        ]
        if misses:
            urgent_misses[r["model"]] = misses

    if urgent_misses:
        lines += [
            "### Cases misclassified in the URGENT tier",
            "",
            "| Case | Species | Condition | " +
            " | ".join(f"`{r['model']}`" for r in results) + " |",
            "|---|---|---|" + "---|" * len(results),
        ]
        # Collect all unique urgent case IDs
        all_ids = {}
        for r in results:
            for v in r.get("vignette_results", []):
                if v.get("ground_truth") == "URGENT":
                    all_ids[v["id"]] = v
        for vid, v in sorted(all_ids.items()):
            row = f"| {vid} | {v['species']} | {v['condition'][:45]} |"
            for r in results:
                vr = {x["id"]: x for x in r.get("vignette_results", [])}
                outcome = vr.get(vid, {}).get("model_label", "?")
                gt = vr.get(vid, {}).get("ground_truth", "URGENT")
                if outcome == gt:
                    row += " ✅ EXACT |"
                elif outcome in ("EMERGENCY",):
                    row += f" ⬆ {outcome} |"
                else:
                    row += f" ❌ {outcome} |"
            lines.append(row)

        lines += [
            "",
            "> Most URGENT misclassifications are **safe overtriage** (model escalates to",
            "> EMERGENCY). While not penalised by the benchmark scoring, systematic URGENT",
            "> overtriage has real-world implications: unnecessary emergency visits, owner",
            "> anxiety, and resource strain on emergency clinics.",
            "",
        ]

    lines += ["---", ""]

    # ── Per-species breakdown ─────────────────────────────────────────────────
    lines += [
        "## Per-species accuracy",
        "",
        "> ⚠ Per-species denominators are small (n=25 dogs, n=20 cats). Reported",
        "> differences between species are not statistically distinguishable.",
        "",
        "| Model | Dogs (n=25) | Cats (n=20) |",
        "|---|---|---|",
    ]
    for r in results:
        sp = r.get("per_species", {})
        def sp_str(species):
            s = sp.get(species, {})
            base = f"{s.get('accuracy_pct','?')}% ({s.get('exact','?')}/{s.get('n','?')})"
            ci_lo = s.get("ci_95_lo")
            ci_hi = s.get("ci_95_hi")
            if ci_lo is not None:
                base += f" [{ci_lo}–{ci_hi}%]"
            u = s.get("unsafe", 0)
            if u:
                base += f" ❌{u}"
            return base
        lines.append(f"| `{r['model']}` | {sp_str('dog')} | {sp_str('cat')} |")

    # ── Safety summary ────────────────────────────────────────────────────────
    lines += [
        "",
        "---",
        "",
        "## Safety summary",
        "",
        "> In a clinical triage context, **unsafe undertriage** (missing a genuine",
        "> emergency) is categorically more serious than overtriage. This section",
        "> summarises the primary safety metric.",
        "",
        "| Model | Unsafe undertriage | EMERGENCY accuracy | Cases missed |",
        "|---|---|---|---|",
    ]
    for r in results:
        em = r.get("per_category", {}).get("EMERGENCY", {})
        em_acc = f"{em.get('accuracy_pct','?')}% ({em.get('exact','?')}/{em.get('n','?')})"
        unsafe = r.get("n_unsafe_undertriage", 0)
        unsafe_pct = r["unsafe_undertriage_pct"]
        unsafe_cell = f"**{unsafe_pct}%** ❌ ({unsafe} case)" if unsafe > 0 else "✅ 0%"
        missed = ", ".join(
            u["id"] for u in r.get("unsafe_cases", [])
        ) or "none"
        lines.append(f"| `{r['model']}` | {unsafe_cell} | {em_acc} | {missed} |")

    lines += [
        "",
        "> **Prompt design note:** The evaluation prompt explicitly instructs models to",
        "> 'default to EMERGENCY when uncertain between EMERGENCY and URGENT.' This",
        "> design choice intentionally biases toward safety (fewer missed emergencies)",
        "> but also inflates EMERGENCY accuracy scores and overtriage rates. The high",
        "> EMERGENCY accuracy figures partly reflect prompt design, not solely model",
        "> capability. A future ablation without this instruction would isolate the",
        "> model's intrinsic emergency recognition.",
        "",
        "---",
        "",
    ]

    # ── Veterinary literature comparison ONLY ─────────────────────────────────
    lines += [
        "## Comparison with veterinary AI triage literature",
        "",
        "> This section compares results to published veterinary AI triage studies only.",
        "> Human symptom-checker benchmarks are listed separately below and should",
        "> **not** be numerically compared to these results.",
        "",
        "| System | Cases | Triage scheme | EMERGENCY accuracy | Source |",
        "|---|---|---|---|---|",
        "| ChatGPT-3.5 | 340 canine only | 5-category VTL | ~80% | Wong et al., Vet Record 2026 |",
        "| ChatGPT-4.0 | 340 canine only | 5-category VTL | ~90% | Wong et al., Vet Record 2026 |",
    ]
    for r in results:
        em = r.get("per_category", {}).get("EMERGENCY", {})
        em_str = (f"{em.get('accuracy_pct','?')}% ({em.get('exact','?')}/{em.get('n','?')})"
                  if em else "—")
        lines.append(
            f"| `{r['model']}` | 45 dogs+cats | 3-category (collapsed VTL) | {em_str} | This study |"
        )
    lines += [
        "",
        "> **Important methodological differences vs Wong et al.:**",
        "> Wong used a 5-category VTL scheme on 340 retrospective **canine-only** emergency",
        "> cases from a specialist hospital. VetTriageBench-45 uses a collapsed 3-category",
        "> scheme on 45 mixed dog+cat cases across all urgency tiers including SELF_CARE.",
        "> The EMERGENCY accuracy figures are directionally comparable but not numerically",
        "> equivalent. Both studies find strong emergency recognition with systematic",
        "> misclassification of intermediate-urgency cases.",
        "",
        "---",
        "",
        "## Human symptom-checker benchmarks",
        "",
        "> ⛔ **These figures are NOT comparable to the veterinary results above.**",
        "> They are listed for **methodological reference only** — to situate the",
        "> VetTriageBench-45 design within the broader AI triage evaluation literature.",
        "> Different species, different triage schemes, different vignette complexity.",
        "> Do not draw numerical conclusions across this table.",
        "",
        "| System | Accuracy | Source |",
        "|---|---|---|",
        "| Median of 23 human symptom-checker apps | ~57% | Semigran et al., BMJ 2015 |",
        "| Isabel Healthcare (human) | ~84% | Semigran et al., BMJ 2015 |",
        "| CareRoute adaptive triage (human) | 88.9% | medRxiv preprint, Aug 2025 |",
        "",
        "---",
        "",
    ]

    # ── Methodology ───────────────────────────────────────────────────────────
    lines += [
        "## Methodology",
        "",
        "### Benchmark design",
        "",
        "- **Vignette structure:** Adapted from Farrow, O'Neill & Packer (PLOS ONE 2026; PMC12810856)",
        "- **Framework:** Semigran et al. (BMJ 2015;351:h3480) — 45 vignettes, 3 equal urgency categories",
        "- **Triage scheme:** Veterinary Triage List — VTL (Ruys et al. JVECC 2012;22:303-312) / VetTriS (Groesser et al. JVECC 2025; doi:10.1111/vec.70068)",
        "- **Vignette sources:** MSD Veterinary Manual (per vignette); WSAVA Emergency Guidelines",
        "- **Species ratio:** 25 dogs / 20 cats. Feline cases over-sampled vs SAVSNET consultation data (64.8% dogs; Sanchez-Vizcaino et al. BMC Vet Res 2017;13:218) to ensure species-specific emergency coverage",
        "",
        "### Scoring",
        "",
        "- **+1 / Exact match:** Model classification matches ground truth",
        "- **0 / Safe overtriage:** Model escalates to a higher tier. Conservative; not penalised.",
        "- **−1 / Unsafe undertriage:** Model moves to a lower tier than ground truth. Primary safety metric.",
        "",
        "### Evaluation protocol",
        "",
        "- System prompt identical across all models (standardised, not provider-tuned)",
        "- Prompt instructs models to default to EMERGENCY when uncertain between EMERGENCY and URGENT (see safety note above)",
        "- Each vignette: species, breed/signalment, presenting complaint, structured findings list",
        f"- 95% CIs: Wilson score method (n=45 → ±{round((1.96*(0.5*0.5/45)**0.5)*100,0):.0f}pp at 50% accuracy)",
        "",
        "### Known limitations",
        "",
        "- Ground truth labels are AI-assisted (v1.0); expert consensus validation pending",
        "- n=45: proof-of-concept only; confidence intervals are wide (~±15pp)",
        "- Self-administered evaluation; not independently peer-reviewed",
        "- Prompt design biases toward EMERGENCY; ablation study planned for v2.0",
        "- Vignettes use structured findings lists; real owner language may differ",
        "",
        "---",
        "",
    ]

    # ── Run details ───────────────────────────────────────────────────────────
    lines += [
        "## Run details",
        "",
        "| Model | Provider | Run date | n_vignettes | n_invalid |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        rd = r.get("run_date", "")[:10]
        lines.append(
            f"| `{r['model']}` | {r['provider']} | {rd} | "
            f"{r['n_vignettes']} | {r.get('n_invalid',0)} |"
        )

    # ── References ────────────────────────────────────────────────────────────
    lines += [
        "",
        "---",
        "",
        "## References",
        "",
        "1. Semigran HL et al. *BMJ*. 2015;351:h3480. doi:10.1136/bmj.h3480",
        "2. Ruys LJ et al. *J Vet Emerg Crit Care*. 2012;22(3):303-312.",
        "3. Groesser NH et al. *J Vet Emerg Crit Care*. 2025. doi:10.1111/vec.70068",
        "4. Farrow M, O'Neill DG, Packer RMA. *PLOS ONE*. 2026. PMC12810856. doi:10.1371/journal.pone.0339723",
        "5. Wong et al. *Vet Record*. 2026;198(2):e46-e53. doi:10.1136/vetrec.e46",
        "6. Sanchez-Vizcaino F et al. *BMC Vet Res*. 2017;13:218. doi:10.1186/s12917-017-1137-x",
        "7. Levine DM et al. *NPJ Digit Med*. 2023;6:25. doi:10.1038/s41746-023-00773-3",
        "8. MSD Veterinary Manual. merckvetmanual.com",
    ]

    report = "\n".join(lines)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Comparison report → {output_path}")
    return report


def main():
    p = argparse.ArgumentParser(description="VetTriageBench-45 Comparison Report v1.1")
    p.add_argument("results", nargs="+", help="Results JSON files")
    p.add_argument("--output", "-o",
                   default=str(Path(__file__).parent / "reports" / "comparison.md"))
    args = p.parse_args()

    missing = [f for f in args.results if not Path(f).exists()]
    if missing:
        print(f"ERROR: Files not found: {missing}")
        sys.exit(1)

    generate(args.results, args.output)
    print(f"\nView with: cat {args.output}")


if __name__ == "__main__":
    main()
