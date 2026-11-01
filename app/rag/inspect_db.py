import chromadb
col = chromadb.PersistentClient(path="chroma_db").get_collection("statutes")
data = col.get(include=["metadatas"])
by_act = {}
for m in data["metadatas"]:
    by_act.setdefault(m["act"], set()).add(m["section"])
for act, secs in by_act.items():
    nums = sorted(secs, key=lambda s: (int(''.join(c for c in s if c.isdigit())), s))
    print(f"\n{act}: {len(nums)} sections")
    print(", ".join(nums))