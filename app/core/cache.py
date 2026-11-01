import hashlib, json, os
from app.core import llm

CACHE_DIR = "llm_cache"
os.makedirs(CACHE_DIR, exist_ok=True)


def cached_ask(prompt: str, system: str = "", max_tokens: int = 2048, model: str = None) -> str:
    key = hashlib.sha256(f"{model or llm.MODEL}|{system}|{prompt}".encode()).hexdigest()
    path = os.path.join(CACHE_DIR, key + ".json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))["reply"]
    reply = llm.ask(prompt, system=system, max_tokens=max_tokens, model=model)
    json.dump({"reply": reply}, open(path, "w", encoding="utf-8"))
    return reply