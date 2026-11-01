import json, re, sys

name = sys.argv[1] if len(sys.argv) > 1 else "contract_01"
truth = json.load(open(f"tests/contracts/{name}truth.json"))["planted_issues"]
found = json.load(open(f"eval/results_{name}.json"))

KEYWORDS = {   # the finding's title or explanation must mention the actual problem
    "I1": ["non-compete", "restraint", "compete", "competing"],
    "I2": ["penalty", "liquidated", "irrespective", "actual loss"],
    "I3": ["unlimited", "uncapped", "no cap", "without limit", "no limit", "one-sided"],
    "I4": ["unilateral", "seat", "number of arbitrators", "appointed by the company", "sole appoint", "independen"],
    "I5": ["without notice", "no notice", "notice period", "one-sided", "unilateral", "mutual"],
}

hit = subst = tp = n_cites = exp_total = 0
for t in truth:
    if t["clause"]:
        match = [f for f in found if f["clause_id"] == f"C{t['clause']}" and f["has_issue"]]
    else:
        match = [f for f in found if f["type"] == t["type"]]
    text = " ".join(f"{f['issue']} {f['explanation']}" for f in match).lower()
    ok_sub = bool(match) and (t["id"] not in KEYWORDS or any(k in text for k in KEYWORDS[t["id"]]))
    hit += bool(match); subst += ok_sub
    refs = {c["ref"] for f in match for c in f["citations"]}
    expected = set(t["statute"])
    tp += len(refs & expected); n_cites += len(refs); exp_total += len(expected)
    status = match[0].get("status") if match else "-"
    print(f"{'DETECTED' if match else 'MISSED  '} {t['id']} {t['type']:<24} names-problem={str(ok_sub):<5} status={status:<16} cites={sorted(refs)}")

print(f"\nDetection (right clause flagged):      {hit}/{len(truth)}")
print(f"Substance (names the actual problem):  {subst}/{len(truth)}")
print(f"Citation recall:    {tp}/{exp_total}")
print(f"Citation precision: {tp}/{n_cites}")