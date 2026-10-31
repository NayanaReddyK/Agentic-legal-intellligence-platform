from app.core.llm import ask
print(ask("In one sentence, what is a non-compete clause?"))

import chromadb
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("BAAI/bge-small-en-v1.5")
print("embedding dim:", len(m.encode("test")))
c = chromadb.PersistentClient(path="chroma_db")
print("chroma ok:", c.heartbeat() is not None)
