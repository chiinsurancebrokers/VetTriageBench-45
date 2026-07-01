# PetAiNurse-45 Veterinary Triage Benchmark

A standardised accuracy benchmark for veterinary AI triage tools,
modelled on the Semigran et al. (*BMJ*, 2015) methodology used to evaluate
human symptom checkers.

## Files

| File | Purpose |
|---|---|
| `vignettes.json` | 45 standardised veterinary case vignettes with ground-truth labels |
| `benchmark.py` | Automated runner — calls the model and scores each vignette |
| `generate_report.py` | Converts results JSON into a publishable markdown report |
| `README.md` | This file |

## Quick Start

```bash
# 1. Run the benchmark (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=sk-ant-...
python benchmark.py

# 2. Generate the human-readable report
python generate_report.py petainurse45_results_YYYYMMDD_HHMM.json

# 3. View results
cat petainurse45_report.md
```

## What the benchmark measures

### Primary metric: Triage accuracy
Percentage of vignettes where the AI's urgency classification exactly matches
the ground truth (EMERGENCY / URGENT / SELF_CARE).

### Safety metric: Unsafe undertriage rate
Percentage of vignettes where the AI **under-escalates** a genuinely urgent
or emergency situation. This is the critical safety signal — undertriage of
a GDV case, a blocked cat, or a permethrin-poisoned cat could be fatal.

### Scoring
| Outcome | Score | Description |
|---|---|---|
| Exact match | +1 | Correct category |
| Safe overtriage | 0 | Escalated higher than necessary (acceptable) |
| Unsafe undertriage | −1 + ⚠️ | Escalated lower than necessary (safety concern) |

## Vignette distribution

| Category | Count | Examples |
|---|---|---|
| EMERGENCY | 15 | GDV, feline urethral obstruction, permethrin toxicosis, haemoabdomen |
| URGENT | 15 | Cruciate rupture, foreign body ingestion, acute pancreatitis, IVDD |
| SELF_CARE | 15 | Hairball vomiting, post-vaccination lethargy, mild soft stool, scooting |

Species: **Dog** (23 vignettes) and **Cat** (22 vignettes)

## Methodology

Based on Semigran HL et al. (*BMJ* 2015;351:h3480) with the triage
classification framework adapted from the Veterinary Triage List (VTL)
(Ruys et al. 2012) and VetTriS (Groesser et al. 2025).

Each vignette includes:
- Species and breed context
- Presenting complaint (owner's words)
- Condensed findings list (structured symptom list)
- Ground-truth triage category
- Clinical rationale and literature source
- Red-flag indicators for the safety metric

## Transparency & limitations

- Self-administered benchmark (not independently peer-reviewed)
- n=45 vignettes (wide confidence intervals; ~±8–9% at 90% accuracy)
- Vignettes authored by the development team, not independently clinician-validated
- Dogs and cats only (rabbits, birds, reptiles excluded)
- Condensed symptom format, not free-form natural language

## Context: published human symptom-checker benchmarks

| System | Accuracy | Source |
|---|---|---|
| Median of 23 apps | ~57% | Semigran 2015 |
| Isabel Healthcare | ~84% | Semigran 2015 |
| CareRoute | 88.9% | medRxiv, Aug 2025 |

⚠️ Direct comparison with these figures is illustrative only — PetAiNurse-45
uses veterinary vignettes, not the Semigran-45 human vignettes.

## References

1. Semigran HL et al. BMJ 2015;351:h3480
2. Ruys LJ et al. J Vet Emerg Crit Care 2012
3. Groesser NH et al. J Vet Emerg Crit Care 2025 (doi:10.1111/vec.70068)
4. Brundage SI et al. Frontiers in Veterinary Science 2026
