import json

for f in json.load(open("eval/results_contract_01.json", encoding="utf-8")):
    if not f["clause_id"]:
        continue
    print(f"\n=== {f['clause_id']} {f['clause_heading']}  has_issue={f['has_issue']}  status={f.get('status')}")
    print("severity:", f["severity"], "| confidence:", f["confidence"])
    print("issue:", f["issue"])
    print("explanation:", f["explanation"])
    print("retrieved:", f.get("retrieved"))
    print("cited:", [c["ref"] for c in f["citations"]], "| dropped:", [c["ref"] for c in f.get("dropped_citations", [])])
    print("quote:", repr(f.get("supporting_quote")))
    print("quote_verified:", f.get("quote_verified"), "| overstated:", f.get("overstated"))