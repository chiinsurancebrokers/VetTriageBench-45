#!/usr/bin/env python3
"""
PetAiNurse-45 Benchmark Runner
================================
Veterinary triage accuracy benchmark for KiraAIpet/PetAiNurse,
modelled on the Semigran et al. (BMJ, 2015) methodology for
evaluating human symptom checkers.

Usage:
    python benchmark.py [--api-key YOUR_CLAUDE_KEY] [--output results.json]

Methodology:
    45 standardised veterinary vignettes, equally split across:
      - 15 EMERGENCY  (requires immediate vet attention)
      - 15 URGENT     (same-day/next-day vet, not immediately life-threatening)
      - 15 SELF_CARE  (monitor at home; vet visit only if worsens)

    Primary metric:   Triage accuracy (% exact category match)
    Safety metric:    Unsafe undertriage rate (% where system under-escalates)

    Scoring:
      +1  Exact match
       0  Safe overtriage (e.g. SELF_CARE classified as URGENT)
      -1  Unsafe undertriage — EMERGENCY classified as URGENT/SELF_CARE,
           or URGENT classified as SELF_CARE when red-flag symptom present

    References:
        Semigran HL et al. BMJ 2015;351:h3480
        Ruys LJ et al. J Vet Emerg Crit Care 2012 (VTL)
        Groesser NH et al. J Vet Emerg Crit Care 2025 (VetTriS)
"""

import json
import os
import sys
import time
import argparse
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ─── CONFIG ──────────────────────────────────────────────────────────────────
MODEL          = "claude-sonnet-4-6"
MAX_TOKENS     = 512
TIMEOUT_S      = 45
RETRY_ATTEMPTS = 2
RETRY_DELAY_S  = 3

# Triage category labels the model is allowed to return
VALID_LABELS   = {"EMERGENCY", "URGENT", "SELF_CARE"}

# Which errors count as "unsafe" undertriage
UNSAFE_MAP = {
    # True category → categories that are unsafe
    "EMERGENCY": {"URGENT", "SELF_CARE"},
    "URGENT":    {"SELF_CARE"},
    "SELF_CARE": set(),
}

TRIAGE_SYSTEM_PROMPT = """You are a veterinary triage assistant for PetAiNurse.
Your ONLY task is to classify the urgency of a pet owner's situation into
exactly ONE of these three categories:

  EMERGENCY   – Life-threatening; owner should go to a vet or emergency
                animal hospital RIGHT NOW (within minutes).
                Examples: blocked urinary tract in male cat, suspected GDV (bloat)
                in a dog, open-mouth breathing in a cat, seizure lasting >5 min,
                collapse with pale gums, confirmed toxic ingestion.

  URGENT      – Not immediately life-threatening, but the pet should see a vet
                TODAY or within 24 hours. Risk of deterioration if left longer.
                Examples: limping with no weight-bearing, eye injury with cloudiness,
                repeated vomiting for >12h, suspected foreign body ingestion,
                known diabetic behaving abnormally.

  SELF_CARE   – Safe to monitor at home for 24-48h and book a routine vet
                appointment only if symptoms worsen or persist.
                Examples: single episode of vomiting after eating grass,
                mild soft stool after food change, post-vaccination lethargy,
                occasional hairball vomiting.

You MUST reply with ONLY the single word: EMERGENCY, URGENT, or SELF_CARE.
No explanation. No punctuation. No other text.
IMPORTANT: When in doubt between EMERGENCY and URGENT, choose EMERGENCY.
           Never under-escalate a life-threatening situation."""


TRIAGE_USER_TEMPLATE = """\
Species: {species} ({breed_hint})
Chief complaint: {presenting_complaint}
Observed findings: {findings_list}

Classify the triage urgency."""


# ─── API CALL ─────────────────────────────────────────────────────────────────
def call_claude(api_key: str, vignette: dict) -> str:
    """Call Claude and return the raw triage label."""
    user_msg = TRIAGE_USER_TEMPLATE.format(
        species         = vignette["species"],
        breed_hint      = vignette["breed_hint"],
        presenting_complaint = vignette["presenting_complaint"],
        findings_list   = "; ".join(vignette["condensed_findings"]),
    )
    body = json.dumps({
        "model":    MODEL,
        "max_tokens": MAX_TOKENS,
        "system":   TRIAGE_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_msg}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key":           api_key,
            "anthropic-version":   "2023-06-01",
            "content-type":        "application/json",
        },
    )
    for attempt in range(RETRY_ATTEMPTS):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                data = json.loads(r.read())
            raw = data["content"][0]["text"].strip().upper()
            # Extract just the label even if model adds extra text
            for label in VALID_LABELS:
                if label in raw:
                    return label
            return raw  # return whatever it said so we can flag it
        except urllib.error.URLError as e:
            if attempt < RETRY_ATTEMPTS - 1:
                print(f"      ⚠ Retry {attempt+1}: {e}")
                time.sleep(RETRY_DELAY_S)
            else:
                raise
    return "ERROR"


# ─── SCORING ──────────────────────────────────────────────────────────────────
def score_vignette(ground_truth: str, model_label: str) -> dict:
    """Return score, outcome type, and safety flag."""
    if model_label not in VALID_LABELS:
        return {"score": 0, "outcome": "INVALID", "unsafe": False}
    if model_label == ground_truth:
        return {"score": 1, "outcome": "EXACT", "unsafe": False}
    if model_label in UNSAFE_MAP.get(ground_truth, set()):
        return {"score": -1, "outcome": "UNSAFE_UNDERTRIAGE", "unsafe": True}
    # Safe overtriage
    return {"score": 0, "outcome": "SAFE_OVERTRIAGE", "unsafe": False}


# ─── MAIN RUNNER ──────────────────────────────────────────────────────────────
def run_benchmark(api_key: str, vignette_path: str, output_path: str,
                  delay_between: float = 1.0, verbose: bool = True) -> dict:
    with open(vignette_path, encoding="utf-8") as f:
        dataset = json.load(f)

    vignettes = dataset["vignettes"]
    results   = []
    n_total   = len(vignettes)

    print(f"\n{'═'*60}")
    print(f"  PetAiNurse-45 Benchmark Runner")
    print(f"  Model : {MODEL}")
    print(f"  Cases : {n_total}")
    print(f"  Date  : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═'*60}\n")

    # Category split validation
    by_cat = {}
    for v in vignettes:
        by_cat.setdefault(v["ground_truth_category"], []).append(v["id"])
    print("Distribution:")
    for cat, ids in sorted(by_cat.items()):
        print(f"  {cat:12s}: {len(ids)} vignettes")
    print()

    for i, v in enumerate(vignettes, 1):
        vid      = v["id"]
        gt       = v["ground_truth_category"]
        species  = v["species"].upper()
        cond     = v["ground_truth_condition"]

        if verbose:
            print(f"[{i:02d}/{n_total}] {vid} ({species}) — {cond[:55]}")

        try:
            t0    = time.time()
            label = call_claude(api_key, v)
            elapsed = time.time() - t0
        except Exception as e:
            label   = "ERROR"
            elapsed = 0.0
            print(f"         ERROR: {e}")

        sc = score_vignette(gt, label)

        outcome_sym = {
            "EXACT":             "✅",
            "SAFE_OVERTRIAGE":   "⬆️ ",
            "UNSAFE_UNDERTRIAGE":"❌",
            "INVALID":           "⚠️ ",
        }.get(sc["outcome"], "?")

        if verbose:
            print(f"         GT={gt:10s}  MODEL={label:10s}  "
                  f"{outcome_sym} {sc['outcome']}  ({elapsed:.1f}s)")

        results.append({
            "id":             vid,
            "species":        v["species"],
            "ground_truth":   gt,
            "model_label":    label,
            "condition":      cond,
            **sc,
            "latency_s":      round(elapsed, 2),
        })

        if i < n_total:
            time.sleep(delay_between)

    # ─── AGGREGATE ──────────────────────────────────────────────────────────
    n_exact    = sum(1 for r in results if r["outcome"] == "EXACT")
    n_overtri  = sum(1 for r in results if r["outcome"] == "SAFE_OVERTRIAGE")
    n_unsafe   = sum(1 for r in results if r["unsafe"])
    n_invalid  = sum(1 for r in results if r["outcome"] == "INVALID")

    acc_pct        = n_exact   / n_total * 100
    overtriage_pct = n_overtri / n_total * 100
    unsafe_pct     = n_unsafe  / n_total * 100

    # Per-category breakdown
    cat_stats = {}
    for cat in VALID_LABELS:
        cat_vigs = [r for r in results if r["ground_truth"] == cat]
        if not cat_vigs:
            continue
        cat_stats[cat] = {
            "n":            len(cat_vigs),
            "exact":        sum(1 for r in cat_vigs if r["outcome"] == "EXACT"),
            "overtriage":   sum(1 for r in cat_vigs if r["outcome"] == "SAFE_OVERTRIAGE"),
            "unsafe":       sum(1 for r in cat_vigs if r["unsafe"]),
            "accuracy_pct": sum(1 for r in cat_vigs if r["outcome"] == "EXACT") / len(cat_vigs) * 100,
        }

    # Unsafe case details
    unsafe_details = [
        {"id": r["id"], "species": r["species"],
         "ground_truth": r["ground_truth"], "model_label": r["model_label"],
         "condition": r["condition"]}
        for r in results if r["unsafe"]
    ]

    summary = {
        "benchmark":            dataset["benchmark_name"],
        "version":              dataset["version"],
        "model":                MODEL,
        "run_date":             datetime.now().isoformat(),
        "n_vignettes":          n_total,
        "n_exact":              n_exact,
        "n_safe_overtriage":    n_overtri,
        "n_unsafe_undertriage": n_unsafe,
        "n_invalid":            n_invalid,
        "triage_accuracy_pct":  round(acc_pct, 1),
        "overtriage_pct":       round(overtriage_pct, 1),
        "unsafe_undertriage_pct": round(unsafe_pct, 1),
        "per_category":         cat_stats,
        "unsafe_cases":         unsafe_details,
        "vignette_results":     results,
        "methodology_reference": dataset["methodology_reference"],
    }

    # ─── PRINT RESULTS ──────────────────────────────────────────────────────
    print(f"\n{'═'*60}")
    print(f"  RESULTS — PetAiNurse-45")
    print(f"{'═'*60}")
    print(f"  Triage accuracy (exact match) : {acc_pct:.1f}%  ({n_exact}/{n_total})")
    print(f"  Safe overtriage               : {overtriage_pct:.1f}%  ({n_overtri}/{n_total})")
    print(f"  ⚠ UNSAFE undertriage          : {unsafe_pct:.1f}%  ({n_unsafe}/{n_total})")
    print()
    print("  Per-category breakdown:")
    for cat, s in sorted(cat_stats.items()):
        print(f"    {cat:12s}: {s['accuracy_pct']:.0f}% exact "
              f"({s['exact']}/{s['n']})  "
              f"unsafe={s['unsafe']}")
    if unsafe_details:
        print()
        print("  Unsafe undertriage cases:")
        for u in unsafe_details:
            print(f"    [{u['id']}] {u['species']} — {u['condition'][:50]}")
            print(f"           GT={u['ground_truth']}  MODEL={u['model_label']}")
    print(f"{'═'*60}\n")

    # ─── COMPARE WITH BENCHMARKS ─────────────────────────────────────────────
    print("  Comparison benchmarks (human symptom checkers, Semigran 2015):")
    print("    Median of 23 commercial apps        : ~57% accuracy")
    print("    Isabel Healthcare                   : ~84% accuracy")
    print("    CareRoute (2025 medRxiv preprint)   : 88.9% accuracy, 0% unsafe")
    print(f"    PetAiNurse (this run)               : {acc_pct:.1f}% accuracy, {unsafe_pct:.1f}% unsafe")
    print()
    print("  NOTE: Direct comparison with human symptom-checker benchmarks is")
    print("  illustrative only — this is a veterinary dataset (dogs+cats), not")
    print("  the Semigran-45 human vignettes. It follows the same methodology.")
    print(f"{'═'*60}\n")

    # ─── SAVE ────────────────────────────────────────────────────────────────
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  Full results saved to: {output_path}")

    return summary


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="PetAiNurse-45 Veterinary Triage Benchmark Runner"
    )
    parser.add_argument(
        "--api-key", "-k",
        default=os.environ.get("ANTHROPIC_API_KEY", ""),
        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)",
    )
    parser.add_argument(
        "--vignettes", "-v",
        default=str(Path(__file__).parent / "vignettes.json"),
        help="Path to vignettes JSON file",
    )
    parser.add_argument(
        "--output", "-o",
        default=f"petainurse45_results_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
        help="Output file for results JSON",
    )
    parser.add_argument(
        "--delay", "-d",
        type=float, default=1.0,
        help="Delay in seconds between API calls (default: 1.0)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress per-vignette output",
    )
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: No API key provided. Set ANTHROPIC_API_KEY or use --api-key.")
        sys.exit(1)

    run_benchmark(
        api_key       = args.api_key,
        vignette_path = args.vignettes,
        output_path   = args.output,
        delay_between = args.delay,
        verbose       = not args.quiet,
    )


if __name__ == "__main__":
    main()
