import json, sys
from collections import defaultdict


def analyze(run_id: str):
    path = f"results/judged_{run_id}.json"
    with open(path) as f:
        results = json.load(f)

    scored = []
    for r in results:
        ns  = r.get("judge", {}).get("natural_score") or 0
        fk  = r.get("scores", {}).get("flesch_kincaid_grade", 10)
        r["composite"] = round(ns * 10 - fk, 2)
        scored.append(r)

    lineage_scores = defaultdict(list)
    for r in scored:
        lineage_scores[r["lineage"]].append(r["composite"])

    print("\n" + "="*60)
    print("LINEAGE PERFORMANCE  (composite = natural*10 - FK_grade)")
    print("="*60)
    ranked = sorted(
        lineage_scores.items(),
        key=lambda x: sum(x[1]) / len(x[1]),
        reverse=True,
    )
    for lineage, scores in ranked:
        avg = sum(scores) / len(scores)
        print(f"  {lineage:<40} avg={avg:>7.2f}   n={len(scores)}")

    print("\n" + "="*60)
    print("SLOT VARIANT PERFORMANCE")
    print("="*60)
    slot_scores = defaultdict(lambda: defaultdict(list))
    for r in scored:
        if r["source"] == "slot_mutation":
            for slot, variant in r["combo"].items():
                slot_scores[slot][variant].append(r["composite"])

    for slot, variants in slot_scores.items():
        print(f"\n  {slot}:")
        for variant, scores in sorted(
            variants.items(),
            key=lambda x: sum(x[1]) / len(x[1]),
            reverse=True,
        ):
            avg = sum(scores) / len(scores)
            print(f"    {variant:<22} avg={avg:>7.2f}   n={len(scores)}")

    print("\n" + "="*60)
    print("READABILITY BY LINEAGE  (FK grade, lower = more readable)")
    print("="*60)
    fk_by_lineage = defaultdict(list)
    for r in scored:
        fk = r.get("scores", {}).get("flesch_kincaid_grade")
        if fk is not None:
            fk_by_lineage[r["lineage"]].append(fk)

    for lineage, vals in sorted(fk_by_lineage.items(),
                                 key=lambda x: sum(x[1])/len(x[1])):
        avg = sum(vals) / len(vals)
        print(f"  {lineage:<40} FK={avg:>5.2f}")

    print("\n" + "="*60)
    print("PATTERN FLAG FREQUENCY")
    print("="*60)
    flag_counts = defaultdict(int)
    for r in scored:
        for flag in r.get("judge", {}).get("pattern_flags", []):
            flag_counts[flag] += 1

    for flag, count in sorted(flag_counts.items(), key=lambda x: -x[1]):
        print(f"  {flag:<28} {count} occurrences")

    print("\n" + "="*60)
    print("TOP 5 OUTPUTS")
    print("="*60)
    top = sorted(scored, key=lambda x: x["composite"], reverse=True)[:5]
    for i, r in enumerate(top, 1):
        fk    = r.get("scores", {}).get("flesch_kincaid_grade", "?")
        ns    = r.get("judge",  {}).get("natural_score", "?")
        flags = r.get("judge",  {}).get("pattern_flags", [])
        note  = r.get("judge",  {}).get("one_line_note", "")
        print(f"\n  #{i}  composite={r['composite']}  "
              f"FK={fk}  natural={ns}")
        print(f"      lineage : {r['lineage']}")
        print(f"      flags   : {flags}")
        print(f"      note    : {note}")
        print(f"      question: {r['question'][:65]}")

    print("\n" + "="*60)
    print("BOTTOM 3 OUTPUTS  (worst performers)")
    print("="*60)
    bottom = sorted(scored, key=lambda x: x["composite"])[:3]
    for i, r in enumerate(bottom, 1):
        fk    = r.get("scores", {}).get("flesch_kincaid_grade", "?")
        ns    = r.get("judge",  {}).get("natural_score", "?")
        flags = r.get("judge",  {}).get("pattern_flags", [])
        print(f"\n  #{i}  composite={r['composite']}  FK={fk}  natural={ns}")
        print(f"      lineage : {r['lineage']}")
        print(f"      flags   : {flags}")
        print(f"      question: {r['question'][:65]}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze(sys.argv[1])
    else:
        print("Usage: python analyze.py <run_id>")
