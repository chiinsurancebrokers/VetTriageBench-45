# VetTriageBench-45 — Multi-Model Comparison Report

**Generated:** 2026-07-02  
**Benchmark version:** 1.0 (report generator v1.1)  
**Vignettes:** 45 standardised veterinary cases (25 dogs / 20 cats)  
**Categories:** 15 EMERGENCY / 15 URGENT / 15 SELF_CARE  
**Models compared:** 2  

> **Validation status (v1.0):** Ground truth labels were drafted with AI assistance
> and cross-checked against MSD Veterinary Manual and VTL/VetTriS triage criteria.
> Formal expert veterinary consensus validation (>=3 practitioners, Cohen's k >=0.60)
> is planned for v2.0. Results should be interpreted as indicative pending that
> validation. n=45 yields 95% CI of approximately +-15pp — differences between
> models should not be over-interpreted.

---

## Overall results

> WARNING: The confidence intervals of all models overlap.
> The observed accuracy differences are **not statistically distinguishable**
> at n=45. No model ranking is implied by the ordering below.

| Model | Provider | Accuracy (95% CI) | Safe overtriage | Unsafe undertriage |
|---|---|---|---|---|
| `gpt-4o` | openai | **80.0%** (36/45) [66.2-89.1%] | 17.8% | **2.2%** FAIL |
| `claude-sonnet-4-6` | claude | **73.3%** (33/45) [59.0-84.0%] | 26.7% | 0.0% PASS |

---

## Per-category accuracy

| Model | EMERGENCY | URGENT | SELF_CARE |
|---|---|---|---|
| `gpt-4o` | 93.3% (14/15) [70.2-98.8%] | 46.7% (7/15) [24.8-69.9%] | 100.0% (15/15) [79.6-100%] |
| `claude-sonnet-4-6` | 100.0% (15/15) [79.6-100%] | 33.3% (5/15) [15.2-58.3%] | 86.7% (13/15) [62.1-96.3%] |

---

## URGENT tier analysis

> The URGENT tier is where **all models consistently underperform**.
> This is the primary clinical weakness identified by this benchmark.

### `gpt-4o`
- Exact match: **7/15 (46.7%)** [CI 24.8-69.9%]
- Misclassified as EMERGENCY (safe overtriage): 8/15
- Misclassified as SELF_CARE (unsafe undertriage): 0/15

### `claude-sonnet-4-6`
- Exact match: **5/15 (33.3%)** [CI 15.2-58.3%]
- Misclassified as EMERGENCY (safe overtriage): 10/15
- Misclassified as SELF_CARE (unsafe undertriage): 0/15

### URGENT cases — per model outcome

| Case | Condition | `gpt-4o` | `claude-sonnet-4-6` |
|---|---|---|---|
| PA016 | Acute lameness – cruciate ligament ruptu | EXACT | EXACT |
| PA017 | Urinary tract infection / feline idiopat | ^OVER | ^OVER |
| PA018 | Acute coughing / cardiac disease exacerb | EXACT | ^OVER |
| PA019 | Diabetic hypoglycaemia – mild | ^OVER | ^OVER |
| PA020 | Acute onset hindlimb weakness / degenera | ^OVER | ^OVER |
| PA021 | Suspected bite wound abscess – systemica | EXACT | EXACT |
| PA022 | Proptosis (eye popped out of socket) – r | ^OVER | ^OVER |
| PA023 | Suspected hepatic lipidosis – not eating | ^OVER | ^OVER |
| PA024 | Acute pancreatitis | EXACT | EXACT |
| PA025 | Traumatic injury after fall – suspected  | ^OVER | ^OVER |
| PA026 | IVDD (Intervertebral Disc Disease) – mil | EXACT | EXACT |
| PA027 | Eye injury – corneal ulceration with dis | EXACT | EXACT |
| PA028 | Ingestion of foreign body – suspected ob | ^OVER | ^OVER |
| PA029 | Hyperthyroidism with acute signs – hyper | EXACT | ^OVER |
| PA030 | Suspected parvovirus (unvaccinated puppy | ^OVER | ^OVER |

> Most URGENT misclassifications are safe overtriage (model escalates to EMERGENCY).
> While not penalised, systematic overtriage has real-world implications: unnecessary
> emergency visits and resource strain on emergency clinics.

---

## Per-species accuracy

> Per-species denominators are small (n=25 dogs, n=20 cats).
> Reported differences are not statistically distinguishable.

| Model | Dogs (n=25) | Cats (n=20) |
|---|---|---|
| `gpt-4o` | 84.0% (21/25) [65.3-93.6%] | 75.0% (15/20) [53.1-88.8%] FAIL:1 |
| `claude-sonnet-4-6` | 76.0% (19/25) [56.6-88.5%] | 70.0% (14/20) [48.1-85.5%] |

---

## Safety summary

> Unsafe undertriage (missing a genuine emergency) is the primary safety metric.

| Model | Unsafe undertriage | EMERGENCY accuracy | Cases missed |
|---|---|---|---|
| `gpt-4o` | **2.2%** FAIL (1 case) | 93.3% (14/15) | PA014 |
| `claude-sonnet-4-6` | 0% PASS | 100.0% (15/15) | none |

> **Prompt design note:** The evaluation prompt instructs models to default to
> EMERGENCY when uncertain. This biases toward safety but inflates EMERGENCY
> accuracy scores and overtriage rates. A future ablation without this
> instruction would isolate intrinsic model capability.

---

## Comparison with veterinary AI triage literature

> Human symptom-checker benchmarks appear in a SEPARATE section below.
> Do NOT compare numbers across the two sections.

| System | Cases | Triage scheme | EMERGENCY accuracy | Source |
|---|---|---|---|---|
| ChatGPT-3.5 | 340 canine | 5-category VTL | ~80% | Wong et al. Vet Record 2026 |
| ChatGPT-4.0 | 340 canine | 5-category VTL | ~90% | Wong et al. Vet Record 2026 |
| `gpt-4o` | 45 dogs+cats | 3-category collapsed VTL | 93.3% (14/15) | This study |
| `claude-sonnet-4-6` | 45 dogs+cats | 3-category collapsed VTL | 100.0% (15/15) | This study |

---

## Human symptom-checker benchmarks (methodological reference ONLY)

> NOT COMPARABLE to veterinary results above.
> Listed only to situate VetTriageBench-45 within the broader AI triage literature.

| System | Accuracy | Source |
|---|---|---|
| Median of 23 human apps | ~57% | Semigran et al. BMJ 2015 |
| Isabel Healthcare (human) | ~84% | Semigran et al. BMJ 2015 |
| CareRoute adaptive (human) | 88.9% | medRxiv preprint Aug 2025 |

---

## Known limitations

- Ground truth labels are AI-assisted (v1.0); expert consensus validation pending
- n=45: proof-of-concept only; CIs are wide (~+-15pp)
- Self-administered evaluation; not independently peer-reviewed
- Prompt design biases toward EMERGENCY (see safety note above)
- Vignettes use structured findings lists; real owner language may differ

---

## References

1. Semigran HL et al. BMJ. 2015;351:h3480.
2. Ruys LJ et al. J Vet Emerg Crit Care. 2012;22(3):303-312.
3. Groesser NH et al. J Vet Emerg Crit Care. 2025. doi:10.1111/vec.70068
4. Farrow M et al. PLOS ONE. 2026. PMC12810856.
5. Wong et al. Vet Record. 2026;198(2):e46-e53.
6. Sanchez-Vizcaino F et al. BMC Vet Res. 2017;13:218.
7. Levine DM et al. NPJ Digit Med. 2023;6:25.
8. MSD Veterinary Manual. merckvetmanual.com