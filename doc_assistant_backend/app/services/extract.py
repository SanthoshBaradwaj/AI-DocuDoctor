import os
from .text_utils import summarize, fake_ner

def naive_extract_from_minio(stream: bytes, filename: str) -> tuple[str, str]:
    text = ""
    ext = os.path.splitext(filename.lower())[1]
    try:
        if ext in (".txt",):
            text = stream.decode("utf-8", errors="ignore")
        else:
            text = f"Uploaded file: {filename} (binary preview not implemented in dev)"
    except Exception as e:
        text = f"[extract error] {e}"
    excerpt = summarize(text, 200)
    return text, excerpt

def build_extracted(body: str):
    return {"summary": summarize(body, 240), "entities": fake_ner(body)}
    