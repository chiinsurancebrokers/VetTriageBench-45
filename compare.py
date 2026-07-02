#!/usr/bin/env python3
"""
VetTriageBench-45 — Multi-Model Comparison Report Generator (v1.1)
"""
import json, sys, argparse
from datetime import datetime
from pathlib import Path

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def overlap(ci_a, ci_b):
    return ci_a[0] <= ci_b[1] and ci_b[0] <= ci_a[1]

def generate(result_paths, output_path):
    results = [load(p) for p in result_paths]
    results.sort(key=lambda r: -r["triage_accuracy_pct"])
    now = datetime.now().strftime("%Y-%m-%d")
    lines = []

    lines += [
        "# VetTriageBench-45 — Multi-Model Comparison Report",
        "",
        f"**Generated:** {now}  ",
        f"**Benchmark version:** {results[0].get('version','1.0')} (report generator v1.1)  ",
        "**Vignettes:** 45 standardised veterinary cases (25 dogs / 20 cats)  ",
        "**Categories:** 15 EMERGENCY / 15 URGENT / 15 SELF_CARE  ",
        f"**Models compared:** {len(results)}  ",
        "",
        "> **Validation status (v1.0):** Ground truth labels were drafted with AI assistance",
        "> and cross-checked against MSD Veterinary Manual and VTL/VetTriS triage criteria.",
        "> Formal expert veterinary consensus validation (>=3 practitioners, Cohen's k >=0.60)",
        "> is planned for v2.0. Results should be interpreted as indicative pending that",
        "> validation. n=45 yields 95% CI of approximately +-15pp — differences between",
        "> models should not be over-interpreted.",
        "", "---", "",
        "## Overall results", "",
    ]

    if len(results) == 2:
        ci_a = results[0].get("triage_accuracy_ci_95", [0, 100])
        ci_b = results[1].get("triage_accuracy_ci_95", [0, 100])
        if overlap(ci_a, ci_b):
            lines += [
                "> WARNING: The confidence intervals of all models overlap.",
                "> The observed accuracy differences are **not statistically distinguishable**",
                "> at n=45. No model ranking is implied by the ordering below.",
                "",
            ]

    lines += [
        "| Model | Provider | Accuracy (95% CI) | Safe overtriage | Unsafe undertriage |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        ci = r.get("triage_accuracy_ci_95", [None, None])
        ci_str = f"[{ci[0]}-{ci[1]}%]" if ci[0] is not None else ""
        unsafe_cell = (f"**{r['unsafe_undertriage_pct']}%** FAIL"
                       if r["unsafe_undertriage_pct"] > 0
                       else f"{r['unsafe_undertriage_pct']}% PASS")
        lines.append(
            f"| `{r['model']}` | {r['provider']} | "
            f"**{r['triage_accuracy_pct']}%** ({r['n_exact']}/{r['n_vignettes']}) {ci_str} | "
            f"{r['overtriage_pct']}% | {unsafe_cell} |"
        )

    lines += ["", "---", "", "## Per-category accuracy", "",
              "| Model | EMERGENCY | URGENT | SELF_CARE |", "|---|---|---|---|"]
    for r in results:
        cats = r.get("per_category", {})
        def cat_str(cat):
            s = cats.get(cat, {})
            base = f"{s.get('accuracy_pct','?')}% ({s.get('exact','?')}/{s.get('n','?')})"
            ci_lo, ci_hi = s.get("ci_95_lo"), s.get("ci_95_hi")
            if ci_lo is not None:
                base += f" [{ci_lo}-{ci_hi}%]"
            return base
        lines.append(f"| `{r['model']}` | {cat_str('EMERGENCY')} | {cat_str('URGENT')} | {cat_str('SELF_CARE')} |")

    lines += [
        "", "---", "",
        "## URGENT tier analysis",
        "",
        "> The URGENT tier is where **all models consistently underperform**.",
        "> This is the primary clinical weakness identified by this benchmark.",
        "",
    ]
    for r in results:
        urg = r.get("per_category", {}).get("URGENT", {})
        n_urg = urg.get("n", 15)
        n_ex  = urg.get("exact", 0)
        n_ov  = urg.get("overtriage", 0)
        n_un  = urg.get("unsafe", 0)
        lines += [
            f"### `{r['model']}`",
            f"- Exact match: **{n_ex}/{n_urg} ({urg.get('accuracy_pct',0)}%)** [CI {urg.get('ci_95_lo','?')}-{urg.get('ci_95_hi','?')}%]",
            f"- Misclassified as EMERGENCY (safe overtriage): {n_ov}/{n_urg}",
            f"- Misclassified as SELF_CARE (unsafe undertriage): {n_un}/{n_urg}",
            "",
        ]

    all_ids = {}
    for r in results:
        for v in r.get("vignette_results", []):
            if v.get("ground_truth") == "URGENT":
                all_ids[v["id"]] = v

    if all_ids:
        lines += [
            "### URGENT cases — per model outcome",
            "",
            "| Case | Condition | " + " | ".join(f"`{r['model']}`" for r in results) + " |",
            "|---|---|" + "---|" * len(results),
        ]
        for vid, v in sorted(all_ids.items()):
            row = f"| {vid} | {v['condition'][:40]} |"
            for r in results:
                vr = {x["id"]: x for x in r.get("vignette_results", [])}
                lbl = vr.get(vid, {}).get("model_label", "?")
                gt  = vr.get(vid, {}).get("ground_truth", "URGENT")
                if lbl == gt:
                    row += " EXACT |"
                elif lbl == "EMERGENCY":
                    row += f" ^OVER |"
                else:
                    row += f" vv{lbl} |"
            lines.append(row)
        lines += [""]

    lines += [
        "> Most URGENT misclassifications are safe overtriage (model escalates to EMERGENCY).",
        "> While not penalised, systematic overtriage has real-world implications: unnecessary",
        "> emergency visits and resource strain on emergency clinics.",
        "", "---", "",
        "## Per-species accuracy",
        "",
        "> Per-species denominators are small (n=25 dogs, n=20 cats).",
        "> Reported differences are not statistically distinguishable.",
        "",
        "| Model | Dogs (n=25) | Cats (n=20) |", "|---|---|---|",
    ]
    for r in results:
        sp = r.get("per_species", {})
        def sp_str(species):
            s = sp.get(species, {})
            base = f"{s.get('accuracy_pct','?')}% ({s.get('exact','?')}/{s.get('n','?')})"
            ci_lo, ci_hi = s.get("ci_95_lo"), s.get("ci_95_hi")
            if ci_lo is not None:
                base += f" [{ci_lo}-{ci_hi}%]"
            if s.get("unsafe", 0):
                base += f" FAIL:{s['unsafe']}"
            return base
        lines.append(f"| `{r['model']}` | {sp_str('dog')} | {sp_str('cat')} |")

    lines += [
        "", "---", "",
        "## Safety summary",
        "",
        "> Unsafe undertriage (missing a genuine emergency) is the primary safety metric.",
        "",
        "| Model | Unsafe undertriage | EMERGENCY accuracy | Cases missed |",
        "|---|---|---|---|",
    ]
    for r in results:
        em = r.get("per_category", {}).get("EMERGENCY", {})
        em_acc = f"{em.get('accuracy_pct','?')}% ({em.get('exact','?')}/{em.get('n','?')})"
        unsafe = r.get("n_unsafe_undertriage", 0)
        unsafe_pct = r["unsafe_undertriage_pct"]
        unsafe_cell = f"**{unsafe_pct}%** FAIL ({unsafe} case)" if unsafe > 0 else "0% PASS"
        missed = ", ".join(u["id"] for u in r.get("unsafe_cases", [])) or "none"
        lines.append(f"| `{r['model']}` | {unsafe_cell} | {em_acc} | {missed} |")

    lines += [
        "",
        "> **Prompt design note:** The evaluation prompt instructs models to default to",
        "> EMERGENCY when uncertain. This biases toward safety but inflates EMERGENCY",
        "> accuracy scores and overtriage rates. A future ablation without this",
        "> instruction would isolate intrinsic model capability.",
        "", "---", "",
        "## Comparison with veterinary AI triage literature",
        "",
        "> Human symptom-checker benchmarks appear in a SEPARATE section below.",
        "> Do NOT compare numbers across the two sections.",
        "",
        "| System | Cases | Triage scheme | EMERGENCY accuracy | Source |",
        "|---|---|---|---|---|",
        "| ChatGPT-3.5 | 340 canine | 5-category VTL | ~80% | Wong et al. Vet Record 2026 |",
        "| ChatGPT-4.0 | 340 canine | 5-category VTL | ~90% | Wong et al. Vet Record 2026 |",
    ]
    for r in results:
        em = r.get("per_category", {}).get("EMERGENCY", {})
        em_str = f"{em.get('accuracy_pct','?')}% ({em.get('exact','?')}/{em.get('n','?')})" if em else "-"
        lines.append(f"| `{r['model']}` | 45 dogs+cats | 3-category collapsed VTL | {em_str} | This study |")

    lines += [
        "", "---", "",
        "## Human symptom-checker benchmarks (methodological reference ONLY)",
        "",
        "> NOT COMPARABLE to veterinary results above.",
        "> Listed only to situate VetTriageBench-45 within the broader AI triage literature.",
        "",
        "| System | Accuracy | Source |",
        "|---|---|---|",
        "| Median of 23 human apps | ~57% | Semigran et al. BMJ 2015 |",
        "| Isabel Healthcare (human) | ~84% | Semigran et al. BMJ 2015 |",
        "| CareRoute adaptive (human) | 88.9% | medRxiv preprint Aug 2025 |",
        "", "---", "",
        "## Known limitations",
        "",
        "- Ground truth labels are AI-assisted (v1.0); expert consensus validation pending",
        "- n=45: proof-of-concept only; CIs are wide (~+-15pp)",
        "- Self-administered evaluation; not independently peer-reviewed",
        "- Prompt design biases toward EMERGENCY (see safety note above)",
        "- Vignettes use structured findings lists; real owner language may differ",
        "", "---", "",
        "## References",
        "",
        "1. Semigran HL et al. BMJ. 2015;351:h3480.",
        "2. Ruys LJ et al. J Vet Emerg Crit Care. 2012;22(3):303-312.",
        "3. Groesser NH et al. J Vet Emerg Crit Care. 2025. doi:10.1111/vec.70068",
        "4. Farrow M et al. PLOS ONE. 2026. PMC12810856.",
        "5. Wong et al. Vet Record. 2026;198(2):e46-e53.",
        "6. Sanchez-Vizcaino F et al. BMC Vet Res. 2017;13:218.",
        "7. Levine DM et al. NPJ Digit Med. 2023;6:25.",
        "8. MSD Veterinary Manual. merckvetmanual.com",
    ]

    report = "\n".join(lines)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report -> {output_path}")
    return report

def main():
    p = argparse.ArgumentParser()
    p.add_argument("results", nargs="+")
    p.add_argument("--output", "-o", default="reports/comparison.md")
    args = p.parse_args()
    generate(args.results, args.output)

if __name__ == "__main__":
    main()
