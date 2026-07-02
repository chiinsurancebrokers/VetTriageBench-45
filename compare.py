#!/usr/bin/env python3
"""
VetTriageBench-45 — Multi-Model Comparison Report Generator
===========================================================
Reads multiple results JSON files and produces a head-to-head
markdown report suitable for preprint or publication appendix.

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


def generate(result_paths, output_path):
    results = [load(p) for p in result_paths]
    results.sort(key=lambda r: -r["triage_accuracy_pct"])

    now    = datetime.now().strftime("%Y-%m-%d")
    lines  = []
    medals = ["🥇", "🥈", "🥉"] + ["  "] * 20

    # ── Header ────────────────────────────────────────────────────────────────
    lines += [
        "# VetTriageBench-45 — Multi-Model Comparison Report",
        "",
        f"**Generated:** {now}  ",
        f"**Benchmark version:** {results[0].get('version','1.0')}  ",
        f"**Vignettes:** 45 standardised veterinary cases (25 dogs / 20 cats)  ",
        f"**Categories:** 15 EMERGENCY / 15 URGENT / 15 SELF_CARE  ",
        f"**Models compared:** {len(results)}  ",
        "",
        "> **Validation status (v1.0):** Ground truth labels were drafted with",
        "> AI assistance and cross-checked against MSD Veterinary Manual and",
        "> VTL/VetTriS triage criteria. Formal expert veterinary consensus",
        "> validation (≥3 practitioners, Cohen's κ ≥0.60) is planned for v2.0.",
        "> Results should be interpreted as indicative pending that validation.",
        "",
        "---",
        "",
    ]

    # ── Head-to-head table ────────────────────────────────────────────────────
    lines += [
        "## Head-to-head results",
        "",
        "| Rank | Model | Provider | Accuracy (95% CI) | Safe overtriage | ⚠ Unsafe undertriage |",
        "|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(results):
        ci = r.get("triage_accuracy_ci_95", [None, None])
        ci_str = (f"[{ci[0]}–{ci[1]}%]" if ci[0] is not None else "")
        unsafe_cell = (f"**{r['unsafe_undertriage_pct']}%** ❌"
                       if r["unsafe_undertriage_pct"] > 0
                       else f"{r['unsafe_undertriage_pct']}% ✅")
        lines.append(
            f"| {medals[i]} {i+1} | `{r['model']}` | {r['provider']} | "
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

    # ── Per-species breakdown ─────────────────────────────────────────────────
    lines += [
        "",
        "---",
        "",
        "## Per-species accuracy",
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

    # ── Key findings ──────────────────────────────────────────────────────────
    winner = results[0]
    safest = min(results, key=lambda r: r["unsafe_undertriage_pct"])
    lines += [
        "",
        "---",
        "",
        "## Key findings",
        "",
        f"- **Highest accuracy:** `{winner['model']}` at {winner['triage_accuracy_pct']}%",
        f"- **Lowest unsafe undertriage:** `{safest['model']}` at {safest['unsafe_undertriage_pct']}%",
    ]
    all_zero_unsafe = all(r["unsafe_undertriage_pct"] == 0 for r in results)
    if all_zero_unsafe:
        lines.append(
            "- ✅ **All models achieved 0% unsafe undertriage** — no EMERGENCY case was "
            "downgraded to URGENT or SELF_CARE, and no URGENT case with red-flag signs "
            "was downgraded to SELF_CARE."
        )
    else:
        unsafe_models = [r["model"] for r in results if r["unsafe_undertriage_pct"] > 0]
        lines.append(f"- ⚠ Models with unsafe undertriage: {', '.join(f'`{m}`' for m in unsafe_models)}")

    lines += [
        "",
        "> **Note on overtriage:** Safe overtriage (classifying URGENT as EMERGENCY, or",
        "> SELF_CARE as URGENT) is conservative and acceptable in a safety-critical",
        "> triage context — the system errs on the side of caution. Only **unsafe",
        "> undertriage** (moving a case to a *lower* tier than ground truth) is",
        "> penalised in this benchmark, reflecting the clinical priority of not",
        "> missing genuine emergencies.",
        "",
        "---",
        "",
    ]

    # ── Comparison with existing literature ──────────────────────────────────
    lines += [
        "## Comparison with published benchmarks",
        "",
        "### Veterinary AI triage (most directly comparable)",
        "",
        "| System | Cases | EMERGENCY accuracy | Overall | Source |",
        "|---|---|---|---|---|",
        "| ChatGPT-3.5 | 340 canine | ~80% | Not reported | Wong et al., Vet Record 2026 |",
        "| ChatGPT-4.0 | 340 canine | ~90% | Not reported | Wong et al., Vet Record 2026 |",
    ]
    for r in results:
        em = r.get("per_category", {}).get("EMERGENCY", {})
        em_str = (f"{em.get('accuracy_pct','?')}% ({em.get('exact','?')}/{em.get('n','?')})"
                  if em else "—")
        lines.append(
            f"| `{r['model']}` (VetTriageBench-45) | 45 dogs+cats | {em_str} | "
            f"{r['triage_accuracy_pct']}% | This study |"
        )

    lines += [
        "",
        "> **Note:** Wong et al. (2026) evaluated ChatGPT on 340 retrospective *canine*",
        "> emergency cases using the 5-category Ruys VTL scheme. VetTriageBench-45 uses",
        "> a collapsed 3-category scheme (EMERGENCY/URGENT/SELF_CARE) and includes both",
        "> dogs and cats. Numerical comparison is indicative only.",
        "",
        "### Human symptom-checker benchmarks (methodological reference)",
        "",
        "| System | Accuracy | Unsafe undertriage | Source |",
        "|---|---|---|---|",
        "| Median of 23 commercial apps | ~57% | Not reported | Semigran et al., BMJ 2015 |",
        "| Isabel Healthcare | ~84% | — | Semigran et al., BMJ 2015 |",
        "| CareRoute (adaptive) | 88.9% | 0% | medRxiv preprint, Aug 2025 |",
    ]
    for r in results:
        unsafe_note = "✅ 0%" if r["unsafe_undertriage_pct"] == 0 else f"⚠ {r['unsafe_undertriage_pct']}%"
        lines.append(
            f"| `{r['model']}` (VetTriageBench-45) | {r['triage_accuracy_pct']}% "
            f"| {unsafe_note} | This study |"
        )
    lines += [
        "",
        "> ⚠ Direct comparison with human-medicine benchmarks is illustrative only.",
        "> VetTriageBench-45 uses veterinary vignettes (dogs + cats); the Semigran-45",
        "> and Levine-48 datasets use human patient vignettes. Methodology follows the",
        "> same framework but datasets are not interchangeable.",
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
        "- **0 / Safe overtriage:** Model escalates to a higher tier (e.g. URGENT → EMERGENCY). Conservative; not penalised.",
        "- **−1 / Unsafe undertriage:** Model moves to a lower tier than ground truth (EMERGENCY → URGENT/SELF_CARE; URGENT → SELF_CARE). Primary safety metric.",
        "",
        "### Evaluation protocol",
        "",
        "- System prompt identical across all models (standardised, not provider-tuned)",
        "- Prompt instructs models to default to EMERGENCY when uncertain between EMERGENCY and URGENT",
        "- Each vignette presented as: species, breed/signalment, presenting complaint, structured findings list",
        f"- 95% confidence intervals computed using Wilson score method (n=45 → ±{round((1.96*(0.5*0.5/45)**0.5)*100,0):.0f}pp at 50% accuracy)",
        "",
        "### Validation status",
        "",
        "- **v1.0 (current):** Ground truth labels AI-assisted (MSD Vet Manual + VTL/VetTriS criteria). Self-administered; not independently peer-reviewed.",
        "- **v2.0 (planned):** Formal expert consensus validation — ≥3 practising veterinarians, independent label assignment, Cohen's κ ≥0.60 inclusion threshold, following Farrow 2026 protocol.",
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
        "1. Semigran HL, Linder JA, Gidengil C, Mehrotra A. Evaluation of symptom checkers for self diagnosis and triage: audit study. *BMJ*. 2015;351:h3480. doi:10.1136/bmj.h3480",
        "2. Ruys LJ, Gunning M, Teske E, Robben JH, Sigrist NE. Evaluation of a veterinary triage list modified from a human five-point triage system in 485 dogs and cats. *J Vet Emerg Crit Care*. 2012;22(3):303-312.",
        "3. Groesser NH et al. Evaluation of a 5-point triage system for veterinary emergency patients in 164 cats and dogs: VetTriS. *J Vet Emerg Crit Care*. 2025. doi:10.1111/vec.70068",
        "4. Farrow M, O'Neill DG, Packer RMA. Development and validation of standardised canine clinical vignettes. *PLOS ONE*. 2026. PMC12810856. doi:10.1371/journal.pone.0339723",
        "5. Wong et al. When used for veterinary triage, artificial intelligence models recognise emergencies but are more likely than veterinary staff to flag non-urgent cases as urgent. *Vet Record*. 2026;198(2):e46-e53. doi:10.1136/vetrec.e46",
        "6. Sanchez-Vizcaino F et al. Epidemiological and clinical features of dogs and cats presented to small animal veterinary practitioners in the UK. *BMC Vet Res*. 2017;13:218. doi:10.1186/s12917-017-1137-x",
        "7. Levine DM et al. Accuracy of a digital symptom-checker for triage and diagnosis. *NPJ Digit Med*. 2023;6:25. doi:10.1038/s41746-023-00773-3",
        "8. MSD Veterinary Manual. merckvetmanual.com (see individual vignette `source_reference` fields in vignettes.json).",
    ]

    report = "\n".join(lines)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Comparison report → {output_path}")
    return report


def main():
    p = argparse.ArgumentParser(description="VetTriageBench-45 Comparison Report")
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
