import sys
import chromadb
from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("BAAI/bge-small-en-v1.5")
_col = chromadb.PersistentClient(path="chroma_db").get_collection("statutes")
PREFIX = "Represent this sentence for searching relevant passages: "


def search(query: str, k: int = 4) -> list[dict]:
    emb = _model.encode(PREFIX + query, normalize_embeddings=True).tolist()
    res = _col.query(query_embeddings=[emb], n_results=k)
    return [
        {"text": d, "meta": m, "distance": dist}
        for d, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]


if __name__ == "__main__":
    for r in search(" ".join(sys.argv[1:])):
        m = r["meta"]
        print(f"\n[{m['act']} {m['year']}, s.{m['section']}: {m['title']}]  dist={r['distance']:.3f}")
        print(r["text"][:300].replace("\n", " "))