import chromadb

col = chromadb.PersistentClient(path="chroma_db").get_collection("statutes")
print("before:", col.count())

for act, sec in [("Indian Contract Act", "90"), ("Arbitration and Conciliation Act", "8B")]:
    col.delete(where={"$and": [{"act": act}, {"section": sec}]})

print("after:", col.count())