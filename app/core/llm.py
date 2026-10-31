import os, time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
_client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
)
MODEL = os.getenv("LLM_MODEL")

def ask(prompt: str, system: str = "", max_tokens: int = 1024, retries: int = 3) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(retries):
        try:
            resp = _client.chat.completions.create(
                model=MODEL, messages=messages,
                max_tokens=max_tokens, temperature=0.1,
            )
            return resp.choices[0].message.content
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt * 5)   # back off on rate limits