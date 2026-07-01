# VetTriageBench-45 — Multi-Model Comparison Report

**Generated:** 2026-07-01  
**Vignettes:** 45 standardised veterinary cases (dogs + cats)  
**Models compared:** 2  

---

## Head-to-Head Results

| Rank | Model | Provider | Accuracy | Safe overtriage | ⚠️ Unsafe undertriage |
|---|---|---|---|---|---|
| 🥇 1 | `gpt-4o` | openai | **86.7%** (39/45) | 13.3% | 0.0% ✅ |
| 🥈 2 | `claude-sonnet-4-6` | claude | **71.1%** (32/45) | 28.9% | 0.0% ✅ |

---

## Per-Category Accuracy

| Model | EMERGENCY | URGENT | SELF_CARE |
|---|---|---|---|
| `gpt-4o` | 100.0% (15/15) | 60.0% (9/15) | 100.0% (15/15) |
| `claude-sonnet-4-6` | 100.0% (15/15) | 26.7% (4/15) | 86.7% (13/15) |

---

## Key Findings

- **Highest accuracy:** `gpt-4o` at 86.7%
- **Lowest unsafe undertriage:** `gpt-4o` at 0.0%
- ✅ **All models achieved 0% unsafe undertriage** — no emergency case was downgraded

> **Note on overtriage:** Safe overtriage (classifying URGENT as EMERGENCY,
> or SELF_CARE as URGENT) is conservative and acceptable in a safety-critical
> context — it means the system errs on the side of caution. Only **unsafe
> undertriage** (missing a genuine emergency) is penalised in this benchmark.

---

## Comparison with Human Symptom-Checker Benchmarks

| System | Accuracy | Unsafe undertriage | Source |
|---|---|---|---|
| Median of 23 commercial apps | ~57% | Not reported | Semigran et al., BMJ 2015 |
| Isabel Healthcare | ~84% | — | Semigran et al., BMJ 2015 |
| CareRoute (adaptive) | 88.9% | 0% | medRxiv preprint, Aug 2025 |
| **`gpt-4o`** (VetTriageBench-45) | **86.7%** | ✅ 0% | This study |
| **`claude-sonnet-4-6`** (VetTriageBench-45) | **71.1%** | ✅ 0% | This study |

> ⚠️ Direct comparison with human benchmarks is illustrative only.
> VetTriageBench-45 uses veterinary vignettes (dogs+cats), not the
> Semigran-45 human vignettes. Methodology follows the same framework.

---

## Methodology

- **45 vignettes**: 15 EMERGENCY / 15 URGENT / 15 SELF_CARE
- **Species**: Dogs (25) and Cats (20)
- **Triage framework**: Veterinary Triage List (Ruys et al. 2012) / VetTriS (Groesser et al. 2025)
- **Scoring**: Exact match = correct; Safe overtriage = acceptable (0 pts); Unsafe undertriage = safety failure (−1 pt)
- **System prompt**: Identical across all models for fair comparison
- **Self-administered**: Not independently peer-reviewed. n=45 (95% CI ~±8–9pp).

---

## Run Details

| Model | Provider | Run date |
|---|---|---|
| `gpt-4o` | openai | 2026-07-01 |
| `claude-sonnet-4-6` | claude | 2026-07-01 |