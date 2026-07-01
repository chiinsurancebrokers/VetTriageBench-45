#!/usr/bin/env python3
"""
PetAiNurse-45 Report Generator
================================
Converts benchmark results JSON into a publishable markdown report
suitable for use as a credibility/marketing asset (blog post, GitHub
README, or medRxiv-style preprint).

Usage:
    python generate_report.py results.json [--output report.md]
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

REPORT_TEMPLATE = """\
# PetAiNurse-45: Veterinary Triage Accuracy Benchmark

**Version:** {version}  
**Run date:** {run_date_display}  
**Model evaluated:** {model}  
**Vignettes:** {n_vignettes} standardised veterinary case scenarios  
**Species:** Dogs and cats  

---

## Summary Results

| Metric | Result |
|---|---|
| **Triage accuracy (exact match)** | **{triage_accuracy_pct}%** ({n_exact}/{n_vignettes}) |
| Safe overtriage (acceptable) | {overtriage_pct}% ({n_safe_overtriage}/{n_vignettes}) |
| ⚠️ Unsafe undertriage | **{unsafe_undertriage_pct}%** ({n_unsafe_undertriage}/{n_vignettes}) |

### Per-Category Accuracy

| Triage category | Vignettes | Exact match | Unsafe undertriage |
|---|---|---|---|
{per_category_rows}

---

## Methodology

### Benchmark design

PetAiNurse-45 is a set of **{n_vignettes} standardised veterinary case vignettes**,
designed in the spirit of the Semigran et al. (2015, *BMJ*) methodology used to evaluate
human-medicine symptom checkers, adapted for veterinary (dog and cat) triage assessment.

Each vignette was authored by the research team and grounded in peer-reviewed
veterinary literature, primarily the **MSD Veterinary Manual** and the
**Veterinary Triage List (VTL)** framework (Ruys et al., 2012) /
**VetTriS** (Groesser et al., 2025), adapted from the human Manchester Triage Scale.

Vignettes are equally distributed across three triage urgency categories:

| Category | Meaning | Veterinary analogue |
|---|---|---|
| **EMERGENCY** | Life-threatening; go now | VTL Red/Orange (0–15 min) |
| **URGENT** | Same-day vet; risk of deterioration | VTL Yellow (30–60 min) |
| **SELF_CARE** | Monitor at home; routine appointment if worsens | VTL Green (>120 min / elective) |

### Evaluation protocol

Each vignette's "condensed findings" (a structured list of symptoms and context,
mirroring the Semigran-45 Condensed Format) were presented to the model via a
standardised system prompt requesting a single-word triage classification.

The system prompt explicitly:
1. Defined all three urgency categories with concrete veterinary examples  
2. Instructed the model to default to the higher urgency tier when uncertain  
3. Required a single-word output only (EMERGENCY, URGENT, or SELF_CARE)

### Scoring

- **+1 / Exact match**: Model classification matches ground truth  
- **0 / Safe overtriage**: Model over-escalates (e.g., SELF_CARE → URGENT). Conservative and acceptable.  
- **−1 / Unsafe undertriage**: Model under-escalates a clinically significant case  
  (EMERGENCY → URGENT or SELF_CARE; URGENT → SELF_CARE where red-flag signs are present).  
  This is the primary safety metric.

### Vignette content

All 45 vignettes cover presentations representative of real-world dog and cat
veterinary consultations, drawn from epidemiological data on common emergency
and non-emergency presentations (Nationwide Pet Insurance, 2024; BluePearl
Veterinary Partners, 2024; Royal Canin Academy epidemiology data).

Emergency vignettes include: GDV/bloat, feline urethral obstruction, xylitol
ingestion, haemoabdomen, respiratory distress, status epilepticus, aortic
thromboembolism, permethrin toxicosis in cats, anticoagulant rodenticide
poisoning, and diabetic ketoacidosis, among others.

Self-care vignettes include: single vomiting episode after grass eating,
hairball vomiting, mild post-vaccination lethargy, soft stool after food
change, and mild reverse sneezing, among others.

---

## Comparison Context

> ⚠️ **Important limitation**: Direct numerical comparison with human-medicine
> symptom-checker benchmarks is illustrative only. PetAiNurse-45 uses veterinary
> vignettes (dogs and cats), not the Semigran-45 human vignettes. It follows the
> same methodological framework but is a distinct, non-interchangeable dataset.

For orientation, published results from human-medicine symptom-checker evaluations
using the Semigran-45 methodology:

| System | Triage accuracy | Unsafe undertriage |
|---|---|---|
| Median of 23 commercial apps (Semigran 2015) | ~57% | Not reported separately |
| Isabel Healthcare (Semigran 2015) | ~84% | — |
| CareRoute (medRxiv preprint, Aug 2025) | 88.9% | 0% |
| **PetAiNurse (this evaluation)** | **{triage_accuracy_pct}%** | **{unsafe_undertriage_pct}%** |

There is no published equivalent veterinary AI triage benchmark against which to
make a direct species-appropriate comparison, to our knowledge — this benchmark
is intended to establish a baseline for future comparisons.

---

## Limitations & Transparency

This evaluation was **self-administered** by the PetAiNurse development team.
It has **not undergone independent peer review**.

Other important limitations:

- **Small sample size**: 45 vignettes provide a meaningful signal but do not
  substitute for a large-scale, externally validated clinical study. Confidence
  intervals are wide at this sample size (95% CI on a 90% accuracy estimate
  for n=45: approximately ±8–9 percentage points).

- **Vignette provenance**: Vignettes were authored by the research team based
  on published literature. They were not created by independent clinicians or
  validated via a Delphi consensus process, as would be expected of a formal
  academic study. Future iterations should incorporate veterinary expert review.

- **Scope limitations**: Only dogs and cats are covered. Rabbits, birds, and
  reptiles (also supported by PetAiNurse) are not included in this benchmark.

- **Condensed format only**: The benchmark uses a structured symptom list, not
  free-form natural-language conversation. Real owner-reported symptoms may be
  less structured, potentially affecting performance.

- **Single model snapshot**: Results reflect a specific model version ({model})
  at the time of evaluation. Performance may change with model updates.

We publish these results and limitations in full in the spirit of the
transparency standards highlighted by Brundage et al. (*Frontiers in Veterinary
Science*, 2026), who found a mean transparency score of only 6.4% across 71
commercial veterinary AI products.

---

## Unsafe Undertriage Cases

{unsafe_section}

---

## Citation

If you reference this benchmark:

> PetAiNurse development team. "PetAiNurse-45: A Veterinary Triage Accuracy
> Benchmark for Dog and Cat Symptom Assessment." v{version}, {run_date_year}.
> [https://github.com/petainurse/benchmark] *(methodology adapted from Semigran
> et al., BMJ 2015;351:h3480)*

---

## References

1. Semigran HL, Linder JA, Gidengil C, Mehrotra A. Evaluation of symptom
   checkers for self diagnosis and triage: audit study. *BMJ*. 2015;351:h3480.
   doi: 10.1136/bmj.h3480

2. Ruys LJ, Gunning M, Teske E, Robben JH, Sigrist NE. Evaluation of a
   veterinary triage list modified from a human five-point triage system in
   485 dogs and cats. *J Vet Emerg Crit Care*. 2012.

3. Groesser NH et al. Evaluation of a 5-point Triage System for Veterinary
   Emergency Patients in 164 Cats and Dogs: VetTriS. *J Vet Emerg Crit Care*.
   2025. doi:10.1111/vec.70068

4. Nationwide Pet Insurance. Top pet claims 2024. *Veterinary Practice News*.
   April 2024.

5. BluePearl Pet Hospital. What's Wrong with My Pet? The 10 Most Common Pet
   Emergencies. 2024. bluepearlvet.com

6. Brundage SI et al. (2026). Transparency of commercial veterinary AI products.
   *Frontiers in Veterinary Science*.

7. MSD Veterinary Manual. merckvetmanual.com (multiple entries — see individual
   vignette citations in vignettes.json).
"""


def build_per_category_rows(per_category: dict) -> str:
    rows = []
    for cat in ("EMERGENCY", "URGENT", "SELF_CARE"):
        if cat not in per_category:
            continue
        s = per_category[cat]
        rows.append(
            f"| {cat} | {s['n']} | {s['accuracy_pct']:.0f}% "
            f"({s['exact']}/{s['n']}) | {s['unsafe']}/{s['n']} |"
        )
    return "\n".join(rows)


def build_unsafe_section(unsafe_cases: list) -> str:
    if not unsafe_cases:
        return "✅ No unsafe undertriage cases were recorded in this run."
    lines = [
        "The following vignettes were classified at a lower urgency tier than the "
        "ground truth, in a way that could delay necessary veterinary care:\n"
    ]
    for u in unsafe_cases:
        lines.append(
            f"- **[{u['id']}]** {u['species'].capitalize()} — *{u['condition']}*  \n"
            f"  Ground truth: **{u['ground_truth']}** → Model classified as: **{u['model_label']}**"
        )
    return "\n".join(lines)


def generate_report(results_path: str, output_path: str) -> str:
    with open(results_path, encoding="utf-8") as f:
        r = json.load(f)

    run_dt = datetime.fromisoformat(r["run_date"]) if "run_date" in r else datetime.now()

    report = REPORT_TEMPLATE.format(
        version               = r.get("version", "1.0"),
        run_date_display      = run_dt.strftime("%Y-%m-%d %H:%M UTC"),
        run_date_year         = run_dt.strftime("%Y"),
        model                 = r.get("model", "claude-sonnet-4-6"),
        n_vignettes           = r["n_vignettes"],
        triage_accuracy_pct   = r["triage_accuracy_pct"],
        n_exact               = r["n_exact"],
        overtriage_pct        = r["overtriage_pct"],
        n_safe_overtriage     = r["n_safe_overtriage"],
        unsafe_undertriage_pct= r["unsafe_undertriage_pct"],
        n_unsafe_undertriage  = r["n_unsafe_undertriage"],
        per_category_rows     = build_per_category_rows(r.get("per_category", {})),
        unsafe_section        = build_unsafe_section(r.get("unsafe_cases", [])),
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report written to: {output_path}")
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Generate PetAiNurse-45 human-readable report from results JSON"
    )
    parser.add_argument("results", help="Path to benchmark results JSON")
    parser.add_argument(
        "--output", "-o",
        default="petainurse45_report.md",
        help="Output markdown file (default: petainurse45_report.md)",
    )
    args = parser.parse_args()

    if not Path(args.results).exists():
        print(f"ERROR: Results file not found: {args.results}")
        sys.exit(1)

    generate_report(args.results, args.output)


if __name__ == "__main__":
    main()
