import json, urllib.request

# Test with no editorOpen at all
payload = {
    "threadId": "t_test4",
    "runId": "r_test4",
    "state": {"editorContent": 'console.log("hello")'},
    "messages": [{"id": "m1", "role": "user", "content": "Hi, start the interview"}],
    "tools": [],
    "context": [],
    "forwardedProps": {},
}

req = urllib.request.Request(
    "http://localhost:8000/",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print("STATUS", r.status, r.headers.get("content-type"))
        data = r.read().decode(errors="replace")
        print(data[:3000])
except Exception as e:
    print("ERR", type(e).__name__, e)
    if hasattr(e, "read"):
        print(e.read().decode())