# VetTriageBench-45 — Multi-Model Comparison Report

**Generated:** 2026-07-02  
**Benchmark version:** 1.0  
**Vignettes:** 45 standardised veterinary cases (25 dogs / 20 cats)  
**Categories:** 15 EMERGENCY / 15 URGENT / 15 SELF_CARE  
**Models compared:** 2  

> **Validation status (v1.0):** Ground truth labels were drafted with
> AI assistance and cross-checked against MSD Veterinary Manual and
> VTL/VetTriS triage criteria. Formal expert veterinary consensus
> validation (≥3 practitioners, Cohen's κ ≥0.60) is planned for v2.0.
> Results should be interpreted as indicative pending that validation.

---

## Head-to-head results

| Rank | Model | Provider | Accuracy (95% CI) | Safe overtriage | ⚠ Unsafe undertriage |
|---|---|---|---|---|---|
| 🥇 1 | `gpt-4o` | openai | **80.0%** (36/45) [66.2–89.1%] | 17.8% | **2.2%** ❌ |
| 🥈 2 | `claude-sonnet-4-6` | claude | **73.3%** (33/45) [59.0–84.0%] | 26.7% | 0.0% ✅ |

---

## Per-category accuracy

| Model | EMERGENCY | URGENT | SELF_CARE |
|---|---|---|---|
| `gpt-4o` | 93.3% (14/15) [70.2–98.8%] | 46.7% (7/15) [24.8–69.9%] | 100.0% (15/15) [79.6–100%] |
| `claude-sonnet-4-6` | 100.0% (15/15) [79.6–100%] | 33.3% (5/15) [15.2–58.3%] | 86.7% (13/15) [62.1–96.3%] |

---

## Per-species accuracy

| Model | Dogs (n=25) | Cats (n=20) |
|---|---|---|
| `gpt-4o` | 84.0% (21/25) [65.3–93.6%] | 75.0% (15/20) [53.1–88.8%] ❌1 |
| `claude-sonnet-4-6` | 76.0% (19/25) [56.6–88.5%] | 70.0% (14/20) [48.1–85.5%] |

---

## Key findings

- **Highest accuracy:** `gpt-4o` at 80.0%
- **Lowest unsafe undertriage:** `claude-sonnet-4-6` at 0.0%
- ⚠ Models with unsafe undertriage: `gpt-4o`

> **Note on overtriage:** Safe overtriage (classifying URGENT as EMERGENCY, or
> SELF_CARE as URGENT) is conservative and acceptable in a safety-critical
> triage context — the system errs on the side of caution. Only **unsafe
> undertriage** (moving a case to a *lower* tier than ground truth) is
> penalised in this benchmark, reflecting the clinical priority of not
> missing genuine emergencies.

---

## Comparison with published benchmarks

### Veterinary AI triage (most directly comparable)

| System | Cases | EMERGENCY accuracy | Overall | Source |
|---|---|---|---|---|
| ChatGPT-3.5 | 340 canine | ~80% | Not reported | Wong et al., Vet Record 2026 |
| ChatGPT-4.0 | 340 canine | ~90% | Not reported | Wong et al., Vet Record 2026 |
| `gpt-4o` (VetTriageBench-45) | 45 dogs+cats | 93.3% (14/15) | 80.0% | This study |
| `claude-sonnet-4-6` (VetTriageBench-45) | 45 dogs+cats | 100.0% (15/15) | 73.3% | This study |

> **Note:** Wong et al. (2026) evaluated ChatGPT on 340 retrospective *canine*
> emergency cases using the 5-category Ruys VTL scheme. VetTriageBench-45 uses
> a collapsed 3-category scheme (EMERGENCY/URGENT/SELF_CARE) and includes both
> dogs and cats. Numerical comparison is indicative only.

### Human symptom-checker benchmarks (methodological reference)

| System | Accuracy | Unsafe undertriage | Source |
|---|---|---|---|
| Median of 23 commercial apps | ~57% | Not reported | Semigran et al., BMJ 2015 |
| Isabel Healthcare | ~84% | — | Semigran et al., BMJ 2015 |
| CareRoute (adaptive) | 88.9% | 0% | medRxiv preprint, Aug 2025 |
| `gpt-4o` (VetTriageBench-45) | 80.0% | ⚠ 2.2% | This study |
| `claude-sonnet-4-6` (VetTriageBench-45) | 73.3% | ✅ 0% | This study |

> ⚠ Direct comparison with human-medicine benchmarks is illustrative only.
> VetTriageBench-45 uses veterinary vignettes (dogs + cats); the Semigran-45
> and Levine-48 datasets use human patient vignettes. Methodology follows the
> same framework but datasets are not interchangeable.

---

## Methodology

### Benchmark design

- **Vignette structure:** Adapted from Farrow, O'Neill & Packer (PLOS ONE 2026; PMC12810856)
- **Framework:** Semigran et al. (BMJ 2015;351:h3480) — 45 vignettes, 3 equal urgency categories
- **Triage scheme:** Veterinary Triage List — VTL (Ruys et al. JVECC 2012;22:303-312) / VetTriS (Groesser et al. JVECC 2025; doi:10.1111/vec.70068)
- **Vignette sources:** MSD Veterinary Manual (per vignette); WSAVA Emergency Guidelines
- **Species ratio:** 25 dogs / 20 cats. Feline cases over-sampled vs SAVSNET consultation data (64.8% dogs; Sanchez-Vizcaino et al. BMC Vet Res 2017;13:218) to ensure species-specific emergency coverage

### Scoring

- **+1 / Exact match:** Model classification matches ground truth
- **0 / Safe overtriage:** Model escalates to a higher tier (e.g. URGENT → EMERGENCY). Conservative; not penalised.
- **−1 / Unsafe undertriage:** Model moves to a lower tier than ground truth (EMERGENCY → URGENT/SELF_CARE; URGENT → SELF_CARE). Primary safety metric.

### Evaluation protocol

- System prompt identical across all models (standardised, not provider-tuned)
- Prompt instructs models to default to EMERGENCY when uncertain between EMERGENCY and URGENT
- Each vignette presented as: species, breed/signalment, presenting complaint, structured findings list
- 95% confidence intervals computed using Wilson score method (n=45 → ±15pp at 50% accuracy)

### Validation status

- **v1.0 (current):** Ground truth labels AI-assisted (MSD Vet Manual + VTL/VetTriS criteria). Self-administered; not independently peer-reviewed.
- **v2.0 (planned):** Formal expert consensus validation — ≥3 practising veterinarians, independent label assignment, Cohen's κ ≥0.60 inclusion threshold, following Farrow 2026 protocol.

---

## Run details

| Model | Provider | Run date | n_vignettes | n_invalid |
|---|---|---|---|---|
| `gpt-4o` | openai | 2026-07-02 | 45 | 0 |
| `claude-sonnet-4-6` | claude | 2026-07-02 | 45 | 0 |

---

## References

1. Semigran HL, Linder JA, Gidengil C, Mehrotra A. Evaluation of symptom checkers for self diagnosis and triage: audit study. *BMJ*. 2015;351:h3480. doi:10.1136/bmj.h3480
2. Ruys LJ, Gunning M, Teske E, Robben JH, Sigrist NE. Evaluation of a veterinary triage list modified from a human five-point triage system in 485 dogs and cats. *J Vet Emerg Crit Care*. 2012;22(3):303-312.
3. Groesser NH et al. Evaluation of a 5-point triage system for veterinary emergency patients in 164 cats and dogs: VetTriS. *J Vet Emerg Crit Care*. 2025. doi:10.1111/vec.70068
4. Farrow M, O'Neill DG, Packer RMA. Development and validation of standardised canine clinical vignettes. *PLOS ONE*. 2026. PMC12810856. doi:10.1371/journal.pone.0339723
5. Wong et al. When used for veterinary triage, artificial intelligence models recognise emergencies but are more likely than veterinary staff to flag non-urgent cases as urgent. *Vet Record*. 2026;198(2):e46-e53. doi:10.1136/vetrec.e46
6. Sanchez-Vizcaino F et al. Epidemiological and clinical features of dogs and cats presented to small animal veterinary practitioners in the UK. *BMC Vet Res*. 2017;13:218. doi:10.1186/s12917-017-1137-x
7. Levine DM et al. Accuracy of a digital symptom-checker for triage and diagnosis. *NPJ Digit Med*. 2023;6:25. doi:10.1038/s41746-023-00773-3
8. MSD Veterinary Manual. merckvetmanual.com (see individual vignette `source_reference` fields in vignettes.json).