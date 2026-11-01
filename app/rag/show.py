import sys, chromadb
col = chromadb.PersistentClient(path="chroma_db").get_collection("statutes")
r = col.get(where={"$and": [{"act": sys.argv[1]}, {"section": sys.argv[2]}]})
for d in r["documents"]:
    print(d[:700], "\n---")