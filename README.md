[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21127218.svg)](https://doi.org/10.5281/zenodo.21127218)

# VetTriageBench-45

**A veterinary triage accuracy benchmark for AI symptom assessment systems**  
**Species:** 25 dogs / 20 cats  |  **Categories:** 15 EMERGENCY / 15 URGENT / 15 SELF_CARE  
**Version:** 1.0  |  **Date:** 2026-07-01

> **Validation status (v1.0):** Ground truth labels were drafted with AI assistance
> and cross-checked against MSD Veterinary Manual and Veterinary Triage List (VTL/VetTriS)
> criteria. Formal expert veterinary consensus validation (≥3 practitioners, Cohen's
> κ ≥0.60, following Farrow et al. 2026) is planned for v2.0. Results should be
> interpreted as indicative pending that validation.

---

## Overview

VetTriageBench-45 is a benchmark for evaluating AI veterinary triage systems,
designed in the spirit of the Semigran et al. (2015, *BMJ*) methodology for
human symptom-checker evaluation, adapted for dogs and cats.

It is, to our knowledge, the first benchmark to cover both dogs and cats across
all urgency tiers (emergency, urgent, self-care). The closest existing resource —
Wong et al. (Vet Record 2026) — evaluated ChatGPT on 340 canine-only emergency
cases. No validated cat-specific veterinary triage vignette bank has been published.

---

## Benchmark results (v1.0)

| Model | Accuracy | 95% CI | Safe overtriage | ⚠ Unsafe undertriage |
|---|---|---|---|---|
| `gpt-4o` | **86.7%** (39/45) | [73.2–94.5%] | 13.3% | ✅ 0% |
| `claude-sonnet-4-6` | **71.1%** (32/45) | [55.7–83.6%] | 28.9% | ✅ 0% |

All models achieved **0% unsafe undertriage** — no EMERGENCY case was downgraded.
Both models show 100% EMERGENCY accuracy with over-triage concentrated in the URGENT
tier, consistent with Wong et al. (2026) findings for ChatGPT on canine cases.

---

## Methodology

### Benchmark design
- **Vignette structure:** Farrow, O'Neill & Packer (*PLOS ONE* 2026; PMC12810856)
- **Framework:** Semigran et al. (*BMJ* 2015;351:h3480) — 45 vignettes, 3 equal urgency categories
- **Triage scheme:** VTL (Ruys et al. *JVECC* 2012;22:303-312) / VetTriS (Groesser et al. *JVECC* 2025)
- **Vignette sources:** MSD Veterinary Manual (per-vignette citations in vignettes.json); WSAVA Emergency Guidelines
- **Species ratio:** 25 dogs / 20 cats — feline cases over-sampled vs SAVSNET consultation data (64.8% dogs; Sanchez-Vizcaino et al. *BMC Vet Res* 2017;13:218) to ensure species-specific emergency coverage

### Scoring
| Outcome | Score | Definition |
|---|---|---|
| Exact match | +1 | Model classification matches ground truth |
| Safe overtriage | 0 | Model escalates to a higher tier — not penalised |
| **Unsafe undertriage** | **−1** | Model moves to a *lower* tier — **primary safety metric** |

### Evaluation
- System prompt identical across all models (no provider-specific tuning)
- Prompt instructs models to default to EMERGENCY when uncertain
- 95% CI computed using Wilson score method

---

## Limitations

1. **Ground truth validation:** Labels are AI-assisted (v1.0), not independently
   validated by veterinary experts. Expert consensus validation planned for v2.0.

2. **Species ratio:** Feline cases (44.4%) over-represented vs real caseload
   (SAVSNET: 30.3% cats). Intentional for coverage; v2.0 target: 30 dogs / 15 cats.

3. **Sample size:** n=45 → 95% CI ≈ ±13pp. Proof-of-concept; not for clinical use.

4. **Scope:** Dogs and cats only. No exotic species.

5. **Self-administered:** Not independently peer-reviewed.

6. **Self-evaluation bias:** Vignettes authored with Claude assistance; interpret
   Claude model results accordingly. GPT-4o provides cross-model reference.

---

## File structure

```
VetTriageBench-45/
├── vignettes.json          # 45 vignettes + full methodology metadata
├── benchmark.py            # Multi-provider runner (Claude / OpenAI / Groq)
├── compare.py              # Head-to-head comparison report generator
├── generate_report.py      # Single-model preprint report generator
├── results/                # JSON output from benchmark.py
│   ├── results_claude_sonnet_4_6_20260701.json
│   └── results_openai_gpt4o_20260701.json
└── reports/                # Markdown reports from generate_report.py / compare.py
```

---

## Usage

```bash
# Run benchmark — Claude
python3 benchmark.py --provider claude --api-key $ANTHROPIC_API_KEY

# Run benchmark — GPT-4o
python3 benchmark.py --provider openai --model gpt-4o --api-key $OPENAI_API_KEY

# Run benchmark — Llama via Groq (free tier)
python3 benchmark.py --provider groq --model llama-3.3-70b-versatile --api-key $GROQ_API_KEY

# Generate head-to-head comparison (all results files)
python3 compare.py results/*.json

# Generate single-model preprint report
python3 generate_report.py results/results_openai_gpt4o_*.json
```

---

## References

1. Semigran HL et al. *BMJ* 2015;351:h3480. doi:10.1136/bmj.h3480
2. Ruys LJ et al. *J Vet Emerg Crit Care* 2012;22:303-312.
3. Groesser NH et al. *J Vet Emerg Crit Care* 2025. doi:10.1111/vec.70068
4. Farrow M, O'Neill DG, Packer RMA. *PLOS ONE* 2026. PMC12810856. doi:10.1371/journal.pone.0339723
5. Wong et al. *Vet Record* 2026;198(2):e46-e53. doi:10.1136/vetrec.e46
6. Sanchez-Vizcaino F et al. *BMC Vet Res* 2017;13:218. doi:10.1186/s12917-017-1137-x
7. Levine DM et al. *NPJ Digit Med* 2023;6:25. doi:10.1038/s41746-023-00773-3

---

## Citation

> Iatropoulos C (KiraAIpet / PetAiNurse development team).
> *VetTriageBench-45: A Veterinary Triage Accuracy Benchmark for AI Symptom
> Assessment Systems.* v1.0, 2026.
> Methodology adapted from Semigran et al., *BMJ* 2015;351:h3480.
