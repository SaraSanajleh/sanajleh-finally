import httpx

payload = {
    "model": "gpt-oss:20b-cloud",
    "stream": False,
    "think": False,
    "messages": [{"role": "user", "content": 'Return only JSON: {"ok": true}'}],
    "options": {"temperature": 0.1, "num_predict": 80},
}
r = httpx.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=120)
print("status", r.status_code)
data = r.json()
msg = data.get("message") or {}
print("content=", repr(msg.get("content")))
print("thinking=", repr((msg.get("thinking") or "")[:300]))
print("keys", list(msg.keys()))
