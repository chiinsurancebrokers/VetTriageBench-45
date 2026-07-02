#!/usr/bin/env python3
"""
VetTriageBench-45 — Multi-Model Benchmark Runner
=================================================
Runs the 45-vignette veterinary triage benchmark across multiple
AI providers (Anthropic Claude, OpenAI GPT, Groq/Llama) for
head-to-head comparison.

Benchmark design
----------------
45 standardised veterinary case vignettes (25 dogs / 20 cats), equally
distributed across three triage urgency categories (15 EMERGENCY /
15 URGENT / 15 SELF_CARE).  Vignette structure follows Farrow, O'Neill &
Packer (PLOS ONE 2026; PMC12810856).  Triage categories align to the
Veterinary Triage List — VTL (Ruys et al., JVECC 2012;22:303-312) and
VetTriS (Groesser et al., JVECC 2025; doi:10.1111/vec.70068).
Benchmark framework adapted from Semigran et al. (BMJ 2015;351:h3480).

Validation status (v1.0)
------------------------
Ground truth labels were drafted with AI assistance and cross-checked
against MSD Veterinary Manual and VTL/VetTriS criteria.  Formal expert
veterinary consensus validation (target >= 3 practitioners, Cohen's
kappa >= 0.60, following the Farrow 2026 protocol) is planned for v2.0.
Results should be interpreted as indicative pending that validation.

Species ratio
-------------
25 dogs (55.6%) / 20 cats (44.4%).  Feline cases are intentionally
over-sampled relative to SAVSNET primary-care consultation data
(64.8% dogs / 30.3% cats; Sanchez-Vizcaino et al., BMC Vet Res
2017;13:218) to ensure adequate coverage of species-specific
emergencies (permethrin toxicosis, aortic thromboembolism, FUO, DKA).

Usage:
    # Claude
    python3 benchmark.py --provider claude --api-key $ANTHROPIC_API_KEY

    # GPT-4o
    python3 benchmark.py --provider openai --model gpt-4o --api-key $OPENAI_API_KEY

    # Llama 3.3 70B via Groq (free tier)
    python3 benchmark.py --provider groq --model llama-3.3-70b-versatile --api-key $GROQ_API_KEY

    # Compare all results
    python3 compare.py results/results_claude*.json results/results_openai*.json

References
----------
1. Semigran HL et al. BMJ 2015;351:h3480. doi:10.1136/bmj.h3480
2. Ruys LJ et al. J Vet Emerg Crit Care 2012;22:303-312.
3. Groesser NH et al. J Vet Emerg Crit Care 2025. doi:10.1111/vec.70068
4. Farrow M, O'Neill DG, Packer RMA. PLOS ONE 2026. PMC12810856.
5. Wong et al. Vet Record 2026;198:e46-e53. doi:10.1136/vetrec.e46
6. Sanchez-Vizcaino F et al. BMC Vet Res 2017;13:218.
7. Levine DM et al. NPJ Digit Med 2023;6:25. doi:10.1038/s41746-023-00773-3
"""

import json, os, sys, time, argparse, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

# ─── DEFAULTS PER PROVIDER ───────────────────────────────────────────────────
PROVIDER_DEFAULTS = {
    "claude": {
        "model":    "claude-sonnet-4-6",
        "endpoint": "https://api.anthropic.com/v1/messages",
        "max_tokens": 16,
    },
    "openai": {
        "model":    "gpt-4o",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "max_tokens": 16,
    },
    "groq": {
        "model":    "llama-3.3-70b-versatile",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "max_tokens": 16,
    },
}

VALID_LABELS   = {"EMERGENCY", "URGENT", "SELF_CARE"}
TIMEOUT_S      = 45
RETRY_ATTEMPTS = 3
RETRY_DELAY_S  = 5

# Undertriage is unsafe when a model moves a case to a LOWER urgency tier.
# EMERGENCY -> URGENT or SELF_CARE = unsafe (could delay life-saving care)
# URGENT -> SELF_CARE = unsafe (risk of deterioration unmanaged)
# Overtriage (moving UP) is never penalised — erring cautious is acceptable.
UNSAFE_UNDERTRIAGE_MAP = {
    "EMERGENCY": {"URGENT", "SELF_CARE"},
    "URGENT":    {"SELF_CARE"},
    "SELF_CARE": set(),
}

# ─── SYSTEM PROMPT ───────────────────────────────────────────────────────────
# Identical across all providers for fair head-to-head comparison.
# Bias toward EMERGENCY when uncertain (safety-first design, consistent
# with the "when in doubt, escalate" principle in VTL/VetTriS).
SYSTEM_PROMPT = """\
You are a veterinary triage assistant.
Your ONLY task is to classify the urgency of a pet owner's situation into
exactly ONE of these three categories:

  EMERGENCY   – Life-threatening; the pet needs a vet or emergency animal
                hospital RIGHT NOW (within minutes). Delay risks death.
                Examples: blocked urinary tract in male cat, GDV/bloat in
                dog, open-mouth breathing in cat, seizure lasting >5 min,
                collapse with pale/white gums, confirmed toxic ingestion,
                uncontrolled haemorrhage, aortic thromboembolism (cat
                suddenly paralysed hind legs, cold, crying), permethrin
                toxicosis in cat.

  URGENT      – Not immediately life-threatening, but the pet should see a
                vet TODAY or within 24 hours. Risk of deterioration if
                delayed beyond 24 h.
                Examples: non-weight-bearing lameness, eye injury with
                cloudiness or discharge, repeated vomiting >12 h, suspected
                swallowed foreign body, diabetic pet acting abnormally,
                suspected bite-wound abscess with fever, cat not eating
                for 2-3 days (hepatic lipidosis risk).

  SELF_CARE   – Safe to monitor at home for 24-48 h; routine vet
                appointment only if symptoms worsen or persist beyond 48-72 h.
                Examples: single vomiting episode after eating grass, mild
                soft stool after food change, post-vaccination lethargy,
                hairball vomiting, minor superficial skin wound, broken nail
                without bleeding, mild sneezing.

Reply with ONLY the single word: EMERGENCY, URGENT, or SELF_CARE.
No explanation. No punctuation. No other text whatsoever.
IMPORTANT: When in doubt between EMERGENCY and URGENT, always choose EMERGENCY.\
"""

USER_TEMPLATE = """\
Species: {species} ({breed_hint})
Chief complaint: {presenting_complaint}
Observed findings: {findings_list}

Classify the triage urgency.\
"""


# ─── API CALLERS ─────────────────────────────────────────────────────────────
def call_claude(api_key, model, endpoint, vignette):
    user_msg = USER_TEMPLATE.format(
        species=vignette["species"],
        breed_hint=vignette["breed_hint"],
        presenting_complaint=vignette["presenting_complaint"],
        findings_list="; ".join(vignette["condensed_findings"]),
    )
    body = json.dumps({
        "model": model,
        "max_tokens": PROVIDER_DEFAULTS["claude"]["max_tokens"],
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_msg}],
    }).encode()
    req = urllib.request.Request(endpoint, data=body, headers={
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.loads(r.read())["content"][0]["text"].strip().upper()


def call_openai_compat(api_key, model, endpoint, vignette):
    """Works for both OpenAI and Groq (same API format)."""
    user_msg = USER_TEMPLATE.format(
        species=vignette["species"],
        breed_hint=vignette["breed_hint"],
        presenting_complaint=vignette["presenting_complaint"],
        findings_list="; ".join(vignette["condensed_findings"]),
    )
    body = json.dumps({
        "model": model,
        "max_tokens": PROVIDER_DEFAULTS["openai"]["max_tokens"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
    }).encode()
    req = urllib.request.Request(endpoint, data=body, headers={
        "Authorization": f"Bearer {api_key}",
        "content-type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip().upper()


def call_model(provider, api_key, model, endpoint, vignette):
    """Call the model with retries. Returns a VALID_LABELS string or 'ERROR'."""
    last_exc = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            if provider == "claude":
                raw = call_claude(api_key, model, endpoint, vignette)
            else:
                raw = call_openai_compat(api_key, model, endpoint, vignette)
            # Accept even if model added surrounding text
            for label in VALID_LABELS:
                if label in raw:
                    return label
            return raw  # Non-standard response — will be flagged INVALID
        except urllib.error.HTTPError as e:
            last_exc = e
            if e.code in (429, 500, 502, 503, 529) and attempt < RETRY_ATTEMPTS - 1:
                wait = RETRY_DELAY_S * (attempt + 1)
                print(f"      ⚠ HTTP {e.code} — retry {attempt+1}/{RETRY_ATTEMPTS-1} in {wait}s")
                time.sleep(wait)
            else:
                raise
        except urllib.error.URLError as e:
            last_exc = e
            if attempt < RETRY_ATTEMPTS - 1:
                print(f"      ⚠ Network error — retry {attempt+1}/{RETRY_ATTEMPTS-1}")
                time.sleep(RETRY_DELAY_S)
            else:
                raise
    return "ERROR"


# ─── SCORING ─────────────────────────────────────────────────────────────────
def score_vignette(ground_truth, model_label):
    """
    Score one vignette result.

    Returns dict with:
      score   : +1 exact, 0 safe overtriage, -1 unsafe undertriage, 0 invalid
      outcome : EXACT | SAFE_OVERTRIAGE | UNSAFE_UNDERTRIAGE | INVALID
      unsafe  : bool — True only for UNSAFE_UNDERTRIAGE
    """
    if model_label not in VALID_LABELS:
        return {"score": 0, "outcome": "INVALID", "unsafe": False}
    if model_label == ground_truth:
        return {"score": 1, "outcome": "EXACT", "unsafe": False}
    if model_label in UNSAFE_UNDERTRIAGE_MAP.get(ground_truth, set()):
        return {"score": -1, "outcome": "UNSAFE_UNDERTRIAGE", "unsafe": True}
    return {"score": 0, "outcome": "SAFE_OVERTRIAGE", "unsafe": False}


# ─── CONFIDENCE INTERVAL ─────────────────────────────────────────────────────
def wilson_ci(k, n, z=1.96):
    """Wilson score interval for a proportion. Returns (lower%, upper%) rounded to 1dp."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = (z * (p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5) / denom
    return (round(max(0, centre - half) * 100, 1),
            round(min(1, centre + half) * 100, 1))


# ─── MAIN RUNNER ─────────────────────────────────────────────────────────────
def run_benchmark(provider, api_key, model, vignette_path, output_path,
                  delay=1.0, verbose=True):
    endpoint = PROVIDER_DEFAULTS[provider]["endpoint"]

    with open(vignette_path, encoding="utf-8") as f:
        dataset = json.load(f)

    vignettes = dataset["vignettes"]
    n = len(vignettes)
    results = []

    label_display = f"{provider}/{model}"
    print(f"\n{'═'*66}")
    print(f"  VetTriageBench-45  |  {label_display}")
    print(f"  Cases: {n}  |  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Validation status: v1.0 — AI-assisted labels, expert review pending")
    print(f"{'═'*66}\n")

    SYM = {
        "EXACT":              "✅",
        "SAFE_OVERTRIAGE":    "⬆ ",
        "UNSAFE_UNDERTRIAGE": "❌",
        "INVALID":            "⚠ ",
    }

    for i, v in enumerate(vignettes, 1):
        gt   = v["ground_truth_category"]
        cond = v["ground_truth_condition"]
        if verbose:
            print(f"[{i:02d}/{n}] {v['id']} ({v['species'].upper()}) — {cond[:52]}")

        try:
            t0      = time.time()
            label   = call_model(provider, api_key, model, endpoint, v)
            elapsed = time.time() - t0
        except Exception as e:
            label, elapsed = "ERROR", 0.0
            print(f"         ERROR: {e}")

        sc = score_vignette(gt, label)
        if verbose:
            print(f"         GT={gt:12s}  MODEL={label:12s}  "
                  f"{SYM.get(sc['outcome'], '?')} {sc['outcome']}  "
                  f"({elapsed:.1f}s)")

        results.append({
            "id":          v["id"],
            "species":     v["species"],
            "ground_truth":gt,
            "model_label": label,
            "condition":   cond,
            "source_reference": v.get("source_reference", ""),
            **sc,
            "latency_s": round(elapsed, 2),
        })
        if i < n:
            time.sleep(delay)

    # ── Aggregate ─────────────────────────────────────────────────────────────
    n_exact   = sum(1 for r in results if r["outcome"] == "EXACT")
    n_over    = sum(1 for r in results if r["outcome"] == "SAFE_OVERTRIAGE")
    n_unsafe  = sum(1 for r in results if r["unsafe"])
    n_invalid = sum(1 for r in results if r["outcome"] == "INVALID")

    # Per-category breakdown
    cat_stats = {}
    for cat in VALID_LABELS:
        cv = [r for r in results if r["ground_truth"] == cat]
        if cv:
            n_cat   = len(cv)
            n_ex    = sum(1 for r in cv if r["outcome"] == "EXACT")
            n_ov    = sum(1 for r in cv if r["outcome"] == "SAFE_OVERTRIAGE")
            n_un    = sum(1 for r in cv if r["unsafe"])
            ci_lo, ci_hi = wilson_ci(n_ex, n_cat)
            cat_stats[cat] = {
                "n":            n_cat,
                "exact":        n_ex,
                "overtriage":   n_ov,
                "unsafe":       n_un,
                "accuracy_pct": round(n_ex / n_cat * 100, 1),
                "ci_95_lo":     ci_lo,
                "ci_95_hi":     ci_hi,
            }

    # Per-species breakdown
    species_stats = {}
    for sp in ("dog", "cat"):
        sv = [r for r in results if r["species"] == sp]
        if sv:
            n_sp = len(sv)
            n_ex = sum(1 for r in sv if r["outcome"] == "EXACT")
            n_un = sum(1 for r in sv if r["unsafe"])
            ci_lo, ci_hi = wilson_ci(n_ex, n_sp)
            species_stats[sp] = {
                "n":            n_sp,
                "exact":        n_ex,
                "unsafe":       n_un,
                "accuracy_pct": round(n_ex / n_sp * 100, 1),
                "ci_95_lo":     ci_lo,
                "ci_95_hi":     ci_hi,
            }

    # Unsafe case details
    unsafe_details = [
        {
            "id":           r["id"],
            "species":      r["species"],
            "ground_truth": r["ground_truth"],
            "model_label":  r["model_label"],
            "condition":    r["condition"],
            "source_reference": r.get("source_reference", ""),
        }
        for r in results if r["unsafe"]
    ]

    # Overall confidence interval
    ci_lo, ci_hi = wilson_ci(n_exact, n)

    summary = {
        # ── Identity ───────────────────────────────────────────────────────
        "benchmark":    dataset["benchmark_name"],
        "version":      dataset["version"],
        "provider":     provider,
        "model":        model,
        "run_date":     datetime.now().isoformat(),

        # ── Methodology metadata ───────────────────────────────────────────
        "methodology": {
            "framework":              "Semigran et al. BMJ 2015;351:h3480",
            "triage_scheme":          "VTL (Ruys et al. JVECC 2012;22:303-312) / VetTriS (Groesser et al. JVECC 2025; doi:10.1111/vec.70068)",
            "vignette_design":        "Farrow, O'Neill & Packer. PLOS ONE 2026; PMC12810856",
            "ai_triage_comparator":   "Wong et al. Vet Record 2026;198:e46-e53. doi:10.1136/vetrec.e46",
            "species_ratio_anchor":   "SAVSNET — Sanchez-Vizcaino et al. BMC Vet Res 2017;13:218",
            "human_benchmark_comparison": "Levine et al. NPJ Digit Med 2023;6:25. doi:10.1038/s41746-023-00773-3",
            "validation_status":      "v1.0 — AI-assisted ground truth labels (MSD Vet Manual + VTL/VetTriS criteria). Formal expert consensus validation (>=3 vets, Cohen's kappa >=0.60) planned for v2.0.",
            "species_ratio_note":     "25 dogs / 20 cats (55.6%/44.4%). Feline cases over-sampled vs SAVSNET (64.8% dogs) to ensure coverage of species-specific emergencies.",
            "n_vignettes":            45,
            "n_emergency":            15,
            "n_urgent":               15,
            "n_self_care":            15,
            "n_dogs":                 25,
            "n_cats":                 20,
        },

        # ── Counts ─────────────────────────────────────────────────────────
        "n_vignettes":              n,
        "n_exact":                  n_exact,
        "n_safe_overtriage":        n_over,
        "n_unsafe_undertriage":     n_unsafe,
        "n_invalid":                n_invalid,

        # ── Primary metrics ────────────────────────────────────────────────
        "triage_accuracy_pct":      round(n_exact / n * 100, 1),
        "triage_accuracy_ci_95":    [ci_lo, ci_hi],
        "overtriage_pct":           round(n_over  / n * 100, 1),
        "unsafe_undertriage_pct":   round(n_unsafe / n * 100, 1),

        # ── Breakdowns ─────────────────────────────────────────────────────
        "per_category":             cat_stats,
        "per_species":              species_stats,

        # ── Detail ─────────────────────────────────────────────────────────
        "unsafe_cases":             unsafe_details,
        "vignette_results":         results,
    }

    # ── Console summary ───────────────────────────────────────────────────────
    print(f"\n{'═'*66}")
    print(f"  RESULTS  |  {label_display}")
    print(f"{'═'*66}")
    print(f"  Triage accuracy (exact)   : {summary['triage_accuracy_pct']}%  "
          f"({n_exact}/{n})  95% CI [{ci_lo}–{ci_hi}%]")
    print(f"  Safe overtriage           : {summary['overtriage_pct']}%  ({n_over}/{n})")
    print(f"  Unsafe undertriage        : {summary['unsafe_undertriage_pct']}%  ({n_unsafe}/{n})")
    if n_invalid:
        print(f"  Invalid / parse failures  : {n_invalid}/{n}")
    print()
    print(f"  Per-category:")
    for cat in ("EMERGENCY", "URGENT", "SELF_CARE"):
        s = cat_stats.get(cat, {})
        print(f"    {cat:12s}: {s.get('accuracy_pct','?')}% "
              f"({s.get('exact','?')}/{s.get('n','?')})  "
              f"CI [{s.get('ci_95_lo','?')}–{s.get('ci_95_hi','?')}%]  "
              f"unsafe={s.get('unsafe','?')}")
    print()
    print(f"  Per-species:")
    for sp in ("dog", "cat"):
        s = species_stats.get(sp, {})
        print(f"    {sp:6s}: {s.get('accuracy_pct','?')}% "
              f"({s.get('exact','?')}/{s.get('n','?')})  "
              f"CI [{s.get('ci_95_lo','?')}–{s.get('ci_95_hi','?')}%]  "
              f"unsafe={s.get('unsafe','?')}")

    if unsafe_details:
        print(f"\n  UNSAFE UNDERTRIAGE CASES:")
        for u in unsafe_details:
            print(f"    [{u['id']}] {u['species']} — {u['condition'][:52]}")
            print(f"           GT={u['ground_truth']}  MODEL={u['model_label']}")
    else:
        print(f"\n  ✅ Zero unsafe undertriage cases.")

    print()
    print(f"  Validation status: AI-assisted labels v1.0 — expert review pending")
    print(f"  Species: {summary['methodology']['n_dogs']} dogs / "
          f"{summary['methodology']['n_cats']} cats "
          f"(SAVSNET anchor: 64.8% dogs in real consultations)")
    print(f"{'═'*66}\n")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  Saved → {output_path}")
    return summary


# ─── CLI ─────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description="VetTriageBench-45 Multi-Model Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 benchmark.py --provider claude --api-key $ANTHROPIC_API_KEY
  python3 benchmark.py --provider openai --model gpt-4o --api-key $OPENAI_API_KEY
  python3 benchmark.py --provider groq   --model llama-3.3-70b-versatile --api-key $GROQ_API_KEY

Validation status note:
  Ground truth labels in v1.0 were drafted with AI assistance.
  Formal expert veterinary consensus validation is planned for v2.0.
  Treat v1.0 results as indicative / preprint-quality.
        """,
    )
    p.add_argument("--provider", "-p", choices=["claude", "openai", "groq"],
                   required=True, help="AI provider")
    p.add_argument("--model", "-m", default=None,
                   help="Model name (default: provider's default)")
    p.add_argument("--api-key", "-k", default=None,
                   help="API key (or set env var: ANTHROPIC_API_KEY / OPENAI_API_KEY / GROQ_API_KEY)")
    p.add_argument("--vignettes", "-v",
                   default=str(Path(__file__).parent / "vignettes.json"),
                   help="Path to vignettes.json")
    p.add_argument("--output", "-o", default=None,
                   help="Output JSON path (default: results/results_{provider}_{model}_{date}.json)")
    p.add_argument("--delay", "-d", type=float, default=1.0,
                   help="Seconds between API calls (default: 1.0)")
    p.add_argument("--quiet", "-q", action="store_true",
                   help="Suppress per-vignette output")
    args = p.parse_args()

    provider = args.provider
    model    = args.model or PROVIDER_DEFAULTS[provider]["model"]
    api_key  = args.api_key

    if not api_key:
        env_map = {
            "claude": ["ANTHROPIC_API_KEY", "Claude_API_Key"],
            "openai": ["OPENAI_API_KEY"],
            "groq":   ["GROQ_API_KEY"],
        }
        for env in env_map[provider]:
            api_key = os.environ.get(env, "")
            if api_key:
                break

    if not api_key:
        print(f"ERROR: No API key for {provider}.")
        print(f"  Use --api-key or set the env var: {env_map[provider][0]}")
        sys.exit(1)

    safe_model = model.replace("/", "_").replace("-", "_")
    datestamp  = datetime.now().strftime("%Y%m%d_%H%M")
    output = (args.output or
              str(Path(__file__).parent / "results" /
                  f"results_{provider}_{safe_model}_{datestamp}.json"))

    run_benchmark(provider, api_key, model, args.vignettes, output,
                  args.delay, not args.quiet)


if __name__ == "__main__":
    main()
