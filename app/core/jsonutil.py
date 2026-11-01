import json, re


def extract_json(text: str):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL)
    text = re.sub(r"```(?:json)?", "", text)
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start == -1:
        raise ValueError("No JSON found in model reply")
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
            continue
        if ch == '"': in_str = True
        elif ch == opener: depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("Unbalanced JSON in model reply")