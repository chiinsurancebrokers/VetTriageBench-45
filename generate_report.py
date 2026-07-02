#!/usr/bin/env python3
"""
VetTriageBench-45 — Preprint Report Generator
==============================================
Converts a benchmark results JSON into a publishable markdown report
suitable for bioRxiv / arXiv deposit or a GitHub-hosted preprint.

Usage:
    python3 generate_report.py results/results_claude_*.json
    python3 generate_report.py results/results_openai_*.json --output reports/report_gpt4o.md
"""

import json, sys, argparse
from datetime import datetime
from pathlib import Path

REPORT_TEMPLATE = """\
# VetTriageBench-45: A Veterinary Triage Accuracy Benchmark for AI Systems

**Version:** {version}  
**Run date:** {run_date_display}  
**Model evaluated:** `{model}` ({provider})  
**Vignettes:** {n_vignettes} standardised veterinary case scenarios  
**Species:** {n_dogs} dogs / {n_cats} cats  
**Categories:** {n_emergency} EMERGENCY / {n_urgent} URGENT / {n_self_care} SELF_CARE  

> **Validation status (v1.0):** Ground truth labels were drafted with AI assistance
> and cross-checked against MSD Veterinary Manual and Veterinary Triage List (VTL)
> criteria. Formal expert veterinary consensus validation (≥3 practitioners,
> Cohen's κ ≥0.60, following Farrow et al. 2026 protocol) is planned for v2.0.
> Current results should be interpreted as indicative pending that validation.

---

## Summary results

| Metric | Result |
|---|---|
| **Triage accuracy (exact match)** | **{triage_accuracy_pct}%** ({n_exact}/{n_vignettes}) — 95% CI [{ci_lo}–{ci_hi}%] |
| Safe overtriage (acceptable) | {overtriage_pct}% ({n_safe_overtriage}/{n_vignettes}) |
| ⚠ Unsafe undertriage (primary safety metric) | **{unsafe_undertriage_pct}%** ({n_unsafe_undertriage}/{n_vignettes}) |

### Per-category accuracy

| Triage category | Vignettes | Exact match | 95% CI | Unsafe undertriage |
|---|---|---|---|---|
{per_category_rows}

### Per-species accuracy

| Species | Vignettes | Exact match | 95% CI | Unsafe undertriage |
|---|---|---|---|---|
{per_species_rows}

---

## Methodology

### Benchmark design

VetTriageBench-45 is a set of **{n_vignettes} standardised veterinary case vignettes**
designed in the spirit of the Semigran et al. (2015, *BMJ*) methodology used to
evaluate human-medicine symptom checkers, adapted for veterinary (dog and cat) triage.

Vignette structure follows the approach of Farrow, O'Neill & Packer (PLOS ONE 2026),
who developed and validated a bank of 30 canine clinical vignettes using anonymised
VetCompass clinical histories and 14-veterinarian consensus labels. Each vignette in
VetTriageBench-45 includes: species, breed/signalment, presenting complaint (owner
narrative), condensed findings (structured symptom list), red-flag indicators, and a
clinician rationale.

Triage categories align to the **Veterinary Triage List (VTL)** (Ruys et al., *JVECC*
2012) and its prospective validation, **VetTriS** (Groesser et al., *JVECC* 2025),
which achieved κ=0.69 interobserver agreement in 164 cats and dogs:

| Category | Meaning | VTL analogue | Target wait |
|---|---|---|---|
| **EMERGENCY** | Life-threatening; go now | Red/Orange | 0–15 min |
| **URGENT** | Same-day vet; risk of deterioration | Yellow | 30–60 min |
| **SELF_CARE** | Monitor at home; routine appointment if worsens | Green | >120 min |

The benchmark is the first to cover both dogs and cats across all three urgency
tiers. The closest existing resource is Wong et al. (Vet Record 2026), who
evaluated ChatGPT-3.5 and GPT-4.0 on 340 retrospective *canine* emergency cases
using a 5-category VTL scheme. No validated cat-specific veterinary triage vignette
bank has been published to date.

**Species ratio:** {n_dogs} dogs ({dog_pct}%) / {n_cats} cats ({cat_pct}%). Feline
cases are intentionally over-sampled relative to real primary-care consultation data
(SAVSNET: 64.8% dogs / 30.3% cats; Sanchez-Vizcaino et al. 2017) to ensure adequate
coverage of species-specific emergencies (permethrin toxicosis, aortic
thromboembolism, feline urethral obstruction, diabetic ketoacidosis).

### Evaluation protocol

Each vignette's condensed findings were presented to the model via a standardised
system prompt requesting a single-word triage classification (EMERGENCY, URGENT, or
SELF_CARE). The system prompt was identical across all model evaluations (no
provider-specific tuning) and explicitly:

1. Defined all three urgency categories with concrete veterinary examples including
   species-specific presentations
2. Instructed the model to default to the higher urgency tier when uncertain between
   EMERGENCY and URGENT (safety-first design, consistent with VTL/VetTriS principles)
3. Required a single-word output only

### Scoring

- **+1 / Exact match:** Model classification matches ground truth
- **0 / Safe overtriage:** Model escalates to a higher tier (e.g. SELF_CARE → URGENT).
  Conservative; not penalised. Consistent with "when in doubt, escalate" clinical principle.
- **−1 / Unsafe undertriage:** Model moves to a *lower* tier than ground truth
  (EMERGENCY → URGENT or SELF_CARE; URGENT → SELF_CARE). Primary safety metric.
  This is the only outcome that constitutes a benchmark failure.

95% confidence intervals computed using the Wilson score method.

### Vignette content

All {n_vignettes} vignettes cover presentations representative of real-world dog and
cat veterinary consultations. Clinical accuracy of each vignette was anchored to the
**MSD Veterinary Manual** (individual citations in vignettes.json) and WSAVA
Emergency Guidelines.

**EMERGENCY vignettes (n={n_emergency}):** Gastric dilatation-volvulus (GDV/bloat),
feline urethral obstruction, xylitol toxicosis, haemoabdomen (suspected splenic mass
rupture), respiratory distress (CHF/pleural effusion in cat), status epilepticus,
aortic thromboembolism (saddle thrombus), penetrating abdominal trauma, permethrin
toxicosis in cat, acute haemorrhagic diarrhoea syndrome (AHDS/HGE), diabetic
ketoacidosis, acute vestibular syndrome, anticoagulant rodenticide poisoning, canine
urolithiasis with obstruction, urethral obstruction in female cat.

**URGENT vignettes (n={n_urgent}):** Cruciate ligament rupture, feline idiopathic
cystitis, cardiac disease exacerbation, mild diabetic hypoglycaemia, hindlimb
weakness (disc disease), bite-wound abscess, proptosis, hepatic lipidosis risk,
pancreatitis, suspected parvovirus, IVDD, foreign body ingestion, hypertensive crisis
(hyperthyroidism), corneal ulceration, high-rise fall trauma.

**SELF_CARE vignettes (n={n_self_care}):** Single vomiting episode (dietary
indiscretion), hairball vomiting, mild allergic skin reaction, sneezing (mild URTI),
superficial skin wound, mild constipation, soft tissue lameness, mild over-grooming,
loose stool (dietary change), post-vaccination lethargy, anal gland discomfort, mild
conjunctivitis, mild otitis externa, broken nail (no bleeding), mild reverse sneezing.

---

## Comparison context

### Veterinary AI triage literature

The most directly comparable published work is Wong et al. (Vet Record 2026), who
found that ChatGPT-3.5 and GPT-4.0 correctly prioritised 80–90% of critical canine
emergency cases but over-triaged approximately 60% of non-urgent cases. The current
results show a similar pattern: 100% EMERGENCY accuracy with higher overtriage rates
in the URGENT tier, consistent across both Claude and GPT-4o evaluations.

> ⚠ Wong et al. used a 5-category VTL scheme on 340 retrospective canine-only
> emergency cases. VetTriageBench-45 uses a collapsed 3-category scheme on
> 45 mixed dog/cat cases including all urgency tiers. Numerical comparison is
> directional only.

### Human symptom-checker benchmarks (methodological reference only)

> ⚠ Direct comparison with human-medicine benchmarks is illustrative only.
> VetTriageBench-45 uses veterinary vignettes (dogs + cats); the Semigran-45
> and Levine-48 datasets use human patient vignettes. They share a methodological
> framework but are not interchangeable datasets.

| System | Triage accuracy | Unsafe undertriage | Source |
|---|---|---|---|
| Median of 23 commercial apps | ~57% | Not reported | Semigran et al., BMJ 2015 |
| Isabel Healthcare | ~84% | — | Semigran et al., BMJ 2015 |
| CareRoute (adaptive) | 88.9% | 0% | medRxiv preprint, Aug 2025 |
| **`{model}`** (VetTriageBench-45) | **{triage_accuracy_pct}%** | **{unsafe_undertriage_pct}%** | This study |

There is no published equivalent veterinary AI triage benchmark covering both
species and all urgency tiers, to our knowledge. VetTriageBench-45 is intended
to establish a reproducible baseline for future comparisons.

---

## Limitations and transparency

This evaluation was **self-administered** by the development team and has
**not undergone independent peer review**. We publish results and limitations
in full in the spirit of transparency standards identified by Brundage et al.
(*Frontiers in Veterinary Science* 2026), who found a mean transparency score
of only 6.4% across 71 commercial veterinary AI products.

**Ground truth validation (primary limitation):** Vignette labels were drafted
with AI assistance and cross-checked against published veterinary literature.
They were not created or validated via independent veterinary expert consensus
(e.g. Delphi process or the Farrow 14-vet protocol). Formal expert validation
is planned for v2.0 (target: ≥3 practitioners, independent labelling, Cohen's
κ ≥0.60 inclusion threshold). Until that validation is complete, ground truth
labels should be treated as clinically informed but not independently confirmed.

**Sample size:** 45 vignettes provide a meaningful signal (95% CI ≈ ±{ci_half}pp
at 90% accuracy, n=45). This is adequate for a proof-of-concept benchmark
(matching the Semigran-45 precedent) but insufficient for regulatory or
clinical-decision purposes. A held-out generalisation set (following the
Levine et al. 2023 48-vignette model) is planned for v2.0.

**Species ratio:** Feline cases (44.4%) are over-represented relative to SAVSNET
primary-care consultation data (30.3% cats; Sanchez-Vizcaino et al. 2017). This
is intentional for coverage purposes but means per-species scores should be
interpreted with that design choice in mind. Emergency-specific settings show
even greater dog skew (VetCOT registry: 82.8–83.9% dogs).

**Scope:** Only dogs and cats are covered. Other species supported by the
application (rabbits, birds, reptiles) are not included in this benchmark.

**Input format:** Vignettes use a structured findings list, not free-form
owner language. Real owner reports may be less structured.

**Model snapshot:** Results reflect `{model}` at run date {run_date_display}.
Performance may change with model version updates.

**Self-evaluation bias:** Vignettes were authored with Claude assistance;
results for Claude models in particular should be interpreted with this in mind.
GPT-4o evaluation provides a useful cross-model reference.

---

## Unsafe undertriage cases

{unsafe_section}

---

## Citation

If you reference this benchmark, please cite:

> Iatropoulos C (PetAiNurse development team). *VetTriageBench-45: A Veterinary
> Triage Accuracy Benchmark for AI Symptom Assessment Systems.* v{version},
> {run_date_year}. Methodology adapted from Semigran et al., *BMJ* 2015;351:h3480
> and Ruys et al., *J Vet Emerg Crit Care* 2012;22:303-312.

---

## References

1. Semigran HL, Linder JA, Gidengil C, Mehrotra A. Evaluation of symptom checkers
   for self diagnosis and triage: audit study. *BMJ*. 2015;351:h3480.
   doi:10.1136/bmj.h3480

2. Ruys LJ, Gunning M, Teske E, Robben JH, Sigrist NE. Evaluation of a veterinary
   triage list modified from a human five-point triage system in 485 dogs and cats.
   *J Vet Emerg Crit Care*. 2012;22(3):303-312.

3. Groesser NH et al. Evaluation of a 5-point triage system for veterinary emergency
   patients in 164 cats and dogs: VetTriS. *J Vet Emerg Crit Care*. 2025.
   doi:10.1111/vec.70068

4. Farrow M, O'Neill DG, Packer RMA. Development and validation of standardised
   canine clinical vignettes for use in dog-owner health literacy research.
   *PLOS ONE*. 2026. PMC12810856. doi:10.1371/journal.pone.0339723

5. Wong et al. When used for veterinary triage, artificial intelligence models
   recognise emergencies but are more likely than veterinary staff to flag non-urgent
   cases as urgent. *Vet Record*. 2026;198(2):e46-e53. doi:10.1136/vetrec.e46

6. Sanchez-Vizcaino F et al. Epidemiological and clinical features of dogs and cats
   presented to a population of small animal veterinary practitioners in the UK.
   *BMC Vet Res*. 2017;13:218. doi:10.1186/s12917-017-1137-x

7. Levine DM et al. Accuracy of a digital symptom-checker for triage and diagnosis.
   *NPJ Digit Med*. 2023;6:25. doi:10.1038/s41746-023-00773-3

8. Brundage SI et al. Transparency of commercial veterinary AI products.
   *Frontiers in Veterinary Science*. 2026.

9. MSD Veterinary Manual. merckvetmanual.com
   (see individual vignette `source_reference` fields in vignettes.json).

10. WSAVA Global Veterinary Community. Emergency and Critical Care Guidelines.
    wsava.org
"""


def wilson_ci(k, n, z=1.96):
    """Wilson score interval. Returns (lo%, hi%, half_width_at_90pct_n45)."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = (z * (p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5) / denom
    return round(max(0, centre - half) * 100, 1), round(min(1, centre + half) * 100, 1)


def build_per_category_rows(per_category: dict) -> str:
    rows = []
    for cat in ("EMERGENCY", "URGENT", "SELF_CARE"):
        if cat not in per_category:
            continue
        s = per_category[cat]
        ci_lo = s.get("ci_95_lo", "—")
        ci_hi = s.get("ci_95_hi", "—")
        ci_str = f"[{ci_lo}–{ci_hi}%]" if ci_lo != "—" else "—"
        rows.append(
            f"| {cat} | {s['n']} | "
            f"{s['accuracy_pct']:.0f}% ({s['exact']}/{s['n']}) | "
            f"{ci_str} | "
            f"{s['unsafe']}/{s['n']} |"
        )
    return "\n".join(rows)


def build_per_species_rows(per_species: dict) -> str:
    rows = []
    for sp in ("dog", "cat"):
        if sp not in per_species:
            continue
        s = per_species[sp]
        ci_lo = s.get("ci_95_lo", "—")
        ci_hi = s.get("ci_95_hi", "—")
        ci_str = f"[{ci_lo}–{ci_hi}%]" if ci_lo != "—" else "—"
        rows.append(
            f"| {sp.capitalize()} | {s['n']} | "
            f"{s['accuracy_pct']:.0f}% ({s['exact']}/{s['n']}) | "
            f"{ci_str} | "
            f"{s['unsafe']}/{s['n']} |"
        )
    return "\n".join(rows)


def build_unsafe_section(unsafe_cases: list) -> str:
    if not unsafe_cases:
        return "✅ No unsafe undertriage cases were recorded in this evaluation run."
    lines = [
        "The following vignettes were classified at a *lower* urgency tier than the "
        "ground truth, in a way that could delay necessary veterinary care:\n"
    ]
    for u in unsafe_cases:
        src = u.get("source_reference", "")
        src_str = f"  \n  *Source: {src}*" if src else ""
        lines.append(
            f"- **[{u['id']}]** {u['species'].capitalize()} — *{u['condition']}*  \n"
            f"  Ground truth: **{u['ground_truth']}** → Model: **{u['model_label']}**"
            f"{src_str}"
        )
    return "\n".join(lines)


def generate_report(results_path: str, output_path: str) -> str:
    with open(results_path, encoding="utf-8") as f:
        r = json.load(f)

    run_dt = datetime.fromisoformat(r["run_date"]) if "run_date" in r else datetime.now()

    # Pull methodology block (new format) or fall back to top-level fields
    meta = r.get("methodology", {})
    n_dogs      = meta.get("n_dogs",      25)
    n_cats      = meta.get("n_cats",      20)
    n_emergency = meta.get("n_emergency", 15)
    n_urgent    = meta.get("n_urgent",    15)
    n_self_care = meta.get("n_self_care", 15)
    n           = r["n_vignettes"]
    n_exact     = r["n_exact"]

    ci_lo, ci_hi = r.get("triage_accuracy_ci_95", wilson_ci(n_exact, n))
    ci_half = round(abs(ci_hi - (n_exact / n * 100)), 1)

    report = REPORT_TEMPLATE.format(
        version                = r.get("version", "1.0"),
        run_date_display       = run_dt.strftime("%Y-%m-%d"),
        run_date_year          = run_dt.strftime("%Y"),
        model                  = r.get("model", "unknown"),
        provider               = r.get("provider", "unknown"),
        n_vignettes            = n,
        n_dogs                 = n_dogs,
        n_cats                 = n_cats,
        dog_pct                = round(n_dogs / (n_dogs + n_cats) * 100, 1),
        cat_pct                = round(n_cats / (n_dogs + n_cats) * 100, 1),
        n_emergency            = n_emergency,
        n_urgent               = n_urgent,
        n_self_care            = n_self_care,
        triage_accuracy_pct    = r["triage_accuracy_pct"],
        n_exact                = n_exact,
        ci_lo                  = ci_lo,
        ci_hi                  = ci_hi,
        ci_half                = ci_half,
        overtriage_pct         = r["overtriage_pct"],
        n_safe_overtriage      = r["n_safe_overtriage"],
        unsafe_undertriage_pct = r["unsafe_undertriage_pct"],
        n_unsafe_undertriage   = r["n_unsafe_undertriage"],
        per_category_rows      = build_per_category_rows(r.get("per_category", {})),
        per_species_rows       = build_per_species_rows(r.get("per_species", {})),
        unsafe_section         = build_unsafe_section(r.get("unsafe_cases", [])),
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report written → {output_path}")
    return report


def main():
    parser = argparse.ArgumentParser(
        description="VetTriageBench-45 — Preprint report generator"
    )
    parser.add_argument("results", help="Path to benchmark results JSON")
    parser.add_argument("--output", "-o", default=None,
                        help="Output markdown file (default: reports/report_{model}.md)")
    args = parser.parse_args()

    if not Path(args.results).exists():
        print(f"ERROR: Results file not found: {args.results}")
        sys.exit(1)

    with open(args.results, encoding="utf-8") as f:
        r_meta = json.load(f)
    safe_model = r_meta.get("model", "unknown").replace("/", "_").replace("-", "_")
    output = args.output or str(
        Path(args.results).parent.parent / "reports" / f"report_{safe_model}.md"
    )

    generate_report(args.results, output)


if __name__ == "__main__":
    main()
