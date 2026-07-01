#!/usr/bin/env python3
"""
VetTriageBench-45 Multi-Model Benchmark Runner
================================================
Runs the 45-vignette veterinary triage benchmark across multiple
AI providers (Anthropic Claude, OpenAI GPT, Groq/Llama) for
head-to-head comparison.

Usage:
    # Claude
    python3 benchmark.py --provider claude --api-key $Claude_API_Key

    # GPT-4o
    python3 benchmark.py --provider openai --model gpt-4o --api-key $OPENAI_API_KEY

    # Llama 3.3 70B via Groq (free tier)
    python3 benchmark.py --provider groq --model llama-3.3-70b-versatile --api-key $GROQ_API_KEY

    # Compare all results
    python3 compare.py results_claude*.json results_openai*.json results_groq*.json
"""

import json, os, sys, time, argparse, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

# ─── DEFAULTS PER PROVIDER ───────────────────────────────────────────────────
PROVIDER_DEFAULTS = {
    "claude": {
        "model":    "claude-sonnet-4-6",
        "endpoint": "https://api.anthropic.com/v1/messages",
        "max_tokens": 512,
    },
    "openai": {
        "model":    "gpt-4o",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "max_tokens": 512,
    },
    "groq": {
        "model":    "llama-3.3-70b-versatile",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "max_tokens": 512,
    },
}

VALID_LABELS   = {"EMERGENCY", "URGENT", "SELF_CARE"}
TIMEOUT_S      = 45
RETRY_ATTEMPTS = 2
RETRY_DELAY_S  = 3

UNSAFE_MAP = {
    "EMERGENCY": {"URGENT", "SELF_CARE"},
    "URGENT":    {"SELF_CARE"},
    "SELF_CARE": set(),
}

SYSTEM_PROMPT = """You are a veterinary triage assistant.
Your ONLY task is to classify the urgency of a pet owner's situation into
exactly ONE of these three categories:

  EMERGENCY   – Life-threatening; go to a vet or emergency animal hospital
                RIGHT NOW (within minutes).
                Examples: blocked urinary tract in male cat, GDV/bloat in dog,
                open-mouth breathing in cat, seizure >5 min, collapse with
                pale gums, confirmed toxic ingestion.

  URGENT      – Not immediately life-threatening, but the pet should see a vet
                TODAY or within 24 hours. Risk of deterioration if left longer.
                Examples: non-weight-bearing lameness, eye injury with cloudiness,
                repeated vomiting >12h, suspected foreign body, diabetic acting
                abnormally.

  SELF_CARE   – Safe to monitor at home 24-48h; routine vet appointment only
                if symptoms worsen or persist.
                Examples: single vomiting episode after eating grass, mild soft
                stool after food change, post-vaccination lethargy, hairball.

Reply with ONLY the single word: EMERGENCY, URGENT, or SELF_CARE.
No explanation. No punctuation. No other text whatsoever.
IMPORTANT: When in doubt between EMERGENCY and URGENT, choose EMERGENCY."""

USER_TEMPLATE = """\
Species: {species} ({breed_hint})
Chief complaint: {presenting_complaint}
Observed findings: {findings_list}

Classify the triage urgency."""


# ─── API CALLERS ──────────────────────────────────────────────────────────────
def call_claude(api_key, model, endpoint, vignette):
    user_msg = USER_TEMPLATE.format(
        species=vignette["species"],
        breed_hint=vignette["breed_hint"],
        presenting_complaint=vignette["presenting_complaint"],
        findings_list="; ".join(vignette["condensed_findings"]),
    )
    body = json.dumps({
        "model": model, "max_tokens": 512,
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
        "model": model, "max_tokens": 512,
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
    raw = ""
    for attempt in range(RETRY_ATTEMPTS):
        try:
            if provider == "claude":
                raw = call_claude(api_key, model, endpoint, vignette)
            else:
                raw = call_openai_compat(api_key, model, endpoint, vignette)
            # Extract label even if model adds extra text
            for label in VALID_LABELS:
                if label in raw:
                    return label
            return raw
        except urllib.error.URLError as e:
            if attempt < RETRY_ATTEMPTS - 1:
                print(f"      ⚠ Retry {attempt+1}: {e}")
                time.sleep(RETRY_DELAY_S)
            else:
                raise
    return "ERROR"


# ─── SCORING ──────────────────────────────────────────────────────────────────
def score(ground_truth, model_label):
    if model_label not in VALID_LABELS:
        return {"score": 0, "outcome": "INVALID", "unsafe": False}
    if model_label == ground_truth:
        return {"score": 1, "outcome": "EXACT", "unsafe": False}
    if model_label in UNSAFE_MAP.get(ground_truth, set()):
        return {"score": -1, "outcome": "UNSAFE_UNDERTRIAGE", "unsafe": True}
    return {"score": 0, "outcome": "SAFE_OVERTRIAGE", "unsafe": False}


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def run_benchmark(provider, api_key, model, vignette_path, output_path,
                  delay=1.0, verbose=True):
    endpoint = PROVIDER_DEFAULTS[provider]["endpoint"]

    with open(vignette_path, encoding="utf-8") as f:
        dataset = json.load(f)

    vignettes = dataset["vignettes"]
    n = len(vignettes)
    results = []

    label_display = f"{provider}/{model}"
    print(f"\n{'═'*62}")
    print(f"  VetTriageBench-45  |  {label_display}")
    print(f"  Cases: {n}  |  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═'*62}\n")

    SYM = {"EXACT":"✅","SAFE_OVERTRIAGE":"⬆️ ","UNSAFE_UNDERTRIAGE":"❌","INVALID":"⚠️ "}

    for i, v in enumerate(vignettes, 1):
        gt   = v["ground_truth_category"]
        cond = v["ground_truth_condition"]
        if verbose:
            print(f"[{i:02d}/{n}] {v['id']} ({v['species'].upper()}) — {cond[:52]}")

        try:
            t0    = time.time()
            label = call_model(provider, api_key, model, endpoint, v)
            elapsed = time.time() - t0
        except Exception as e:
            label, elapsed = "ERROR", 0.0
            print(f"         ERROR: {e}")

        sc = score(gt, label)
        if verbose:
            print(f"         GT={gt:10s}  MODEL={label:10s}  "
                  f"{SYM.get(sc['outcome'],'?')} {sc['outcome']}  ({elapsed:.1f}s)")

        results.append({"id":v["id"],"species":v["species"],"ground_truth":gt,
                        "model_label":label,"condition":cond,**sc,
                        "latency_s":round(elapsed,2)})
        if i < n:
            time.sleep(delay)

    # Aggregate
    n_exact   = sum(1 for r in results if r["outcome"]=="EXACT")
    n_over    = sum(1 for r in results if r["outcome"]=="SAFE_OVERTRIAGE")
    n_unsafe  = sum(1 for r in results if r["unsafe"])
    n_invalid = sum(1 for r in results if r["outcome"]=="INVALID")

    cat_stats = {}
    for cat in VALID_LABELS:
        cv = [r for r in results if r["ground_truth"]==cat]
        if cv:
            cat_stats[cat] = {
                "n":len(cv),
                "exact":sum(1 for r in cv if r["outcome"]=="EXACT"),
                "overtriage":sum(1 for r in cv if r["outcome"]=="SAFE_OVERTRIAGE"),
                "unsafe":sum(1 for r in cv if r["unsafe"]),
                "accuracy_pct":round(sum(1 for r in cv if r["outcome"]=="EXACT")/len(cv)*100,1),
            }

    unsafe_details = [{"id":r["id"],"species":r["species"],
                       "ground_truth":r["ground_truth"],"model_label":r["model_label"],
                       "condition":r["condition"]} for r in results if r["unsafe"]]

    summary = {
        "benchmark": dataset["benchmark_name"],
        "version": dataset["version"],
        "provider": provider,
        "model": model,
        "run_date": datetime.now().isoformat(),
        "n_vignettes": n,
        "n_exact": n_exact,
        "n_safe_overtriage": n_over,
        "n_unsafe_undertriage": n_unsafe,
        "n_invalid": n_invalid,
        "triage_accuracy_pct": round(n_exact/n*100,1),
        "overtriage_pct": round(n_over/n*100,1),
        "unsafe_undertriage_pct": round(n_unsafe/n*100,1),
        "per_category": cat_stats,
        "unsafe_cases": unsafe_details,
        "vignette_results": results,
    }

    print(f"\n{'═'*62}")
    print(f"  RESULTS  |  {label_display}")
    print(f"{'═'*62}")
    print(f"  Triage accuracy (exact)   : {summary['triage_accuracy_pct']}%  ({n_exact}/{n})")
    print(f"  Safe overtriage           : {summary['overtriage_pct']}%  ({n_over}/{n})")
    print(f"  ⚠ UNSAFE undertriage      : {summary['unsafe_undertriage_pct']}%  ({n_unsafe}/{n})")
    print()
    for cat, s in sorted(cat_stats.items()):
        print(f"    {cat:12s}: {s['accuracy_pct']}% exact ({s['exact']}/{s['n']})  unsafe={s['unsafe']}")
    if unsafe_details:
        print("\n  UNSAFE CASES:")
        for u in unsafe_details:
            print(f"    [{u['id']}] {u['species']} — {u['condition'][:50]}")
            print(f"           GT={u['ground_truth']}  MODEL={u['model_label']}")
    print(f"{'═'*62}\n")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  Saved → {output_path}")
    return summary


# ─── CLI ─────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="VetTriageBench-45 Multi-Model Runner")
    p.add_argument("--provider", "-p", choices=["claude","openai","groq"],
                   required=True, help="AI provider")
    p.add_argument("--model", "-m", default=None,
                   help="Model name (default: provider's default)")
    p.add_argument("--api-key", "-k", default=None,
                   help="API key (or set env var)")
    p.add_argument("--vignettes", "-v",
                   default=str(Path(__file__).parent/"vignettes.json"))
    p.add_argument("--output", "-o", default=None)
    p.add_argument("--delay", "-d", type=float, default=1.0)
    p.add_argument("--quiet", "-q", action="store_true")
    args = p.parse_args()

    provider = args.provider
    model    = args.model or PROVIDER_DEFAULTS[provider]["model"]
    api_key  = args.api_key

    # Fallback to common env var names
    if not api_key:
        env_map = {
            "claude": ["Claude_API_Key","ANTHROPIC_API_KEY"],
            "openai": ["OPENAI_API_KEY"],
            "groq":   ["GROQ_API_KEY"],
        }
        for env in env_map[provider]:
            api_key = os.environ.get(env,"")
            if api_key: break

    if not api_key:
        print(f"ERROR: No API key for {provider}. Use --api-key or set env var.")
        sys.exit(1)

    output = args.output or f"/tmp/results_{provider}_{model.replace('/','_').replace('-','_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"

    run_benchmark(provider, api_key, model, args.vignettes, output,
                  args.delay, not args.quiet)


if __name__ == "__main__":
    main()
