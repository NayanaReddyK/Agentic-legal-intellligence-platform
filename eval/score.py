import json, sys

names = sys.argv[1:] or ["contract_01"]
T = dict(hit=0, subst=0, sev=0, n=0, stat_hit=0, stat_n=0, tp=0, cites=0)
all_fp = []

for name in names:
    truth = json.load(open(f"tests/contracts/{name}truth.json"))["planted_issues"]
    found = json.load(open(f"eval/results_{name}.json"))
    print(f"\n===== {name} =====")
    for t in truth:
        if t["clause"]:
            match = [f for f in found if f["clause_id"] == f"C{t['clause']}" and f["has_issue"]]
        else:
            match = [f for f in found if f["type"] == t["type"]]
        text = " ".join(f"{f['issue']} {f['explanation']}" for f in match).lower()
        kw = t.get("keywords") or []
        ok_sub = bool(match) and (not kw or any(k in text for k in kw))
        ok_sev = bool(match) and match[0]["severity"] == t["severity"]
        refs = {c["ref"] for f in match for c in f["citations"]}
        expected = set(t["statute"])
        T["n"] += 1; T["hit"] += bool(match); T["subst"] += ok_sub; T["sev"] += ok_sev
        T["tp"] += len(refs & expected); T["cites"] += len(refs)
        if t.get("basis") == "statutory":
            T["stat_n"] += 1; T["stat_hit"] += bool(expected) and expected <= refs
        status = (match[0].get("status") or "-") if match else "-"
        print(f"{'DETECTED' if match else 'MISSED  '} {t['id']} {t['type']:<24} names-problem={str(ok_sub):<5} severity-ok={str(ok_sev):<5} status={status:<16} cites={sorted(refs)}")
    planted = {t["clause"] for t in truth if t["clause"]}
    fp = [(f["clause_id"], f["issue"]) for f in found
          if f["has_issue"] and f["clause_id"] and f["clause_id"][1:] not in planted]
    all_fp += [(name,) + x for x in fp]
    print("Flagged clauses NOT in answer key (possible false positives, judge by hand):", fp or "none")

print("\n===== TOTAL =====")
print(f"Detection (right clause flagged):         {T['hit']}/{T['n']}")
print(f"Substance (names the actual problem):     {T['subst']}/{T['n']}")
print(f"Severity matches answer key:              {T['sev']}/{T['n']}")
print(f"Statutory issues with all statutes cited: {T['stat_hit']}/{T['stat_n']}")
print(f"Citation precision (cited in key):        {T['tp']}/{T['cites']}")
print(f"Possible false positives:                 {len(all_fp)}")
