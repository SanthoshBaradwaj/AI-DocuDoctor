def summarize(text: str, limit: int = 160) -> str:
    clean = " ".join(text.split())
    return clean[:limit] + ("…" if len(clean) > limit else "")

def fake_ner(text: str):
    return [{"type":"TOKEN_COUNT","value":len(text.split())}]
