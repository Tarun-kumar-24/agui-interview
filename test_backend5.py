import json, urllib.request

# Test with editorOpen = false initially, then the agent should call open_editor
payload = {
    "threadId": "t_test5",
    "runId": "r_test5",
    "state": {"editorContent": 'console.log("hello")', "editorOpen": False},
    "messages": [{"id": "m1", "role": "user", "content": "Hi, I want to do a coding challenge"}],
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
        print(data[:5000])
except Exception as e:
    print("ERR", type(e).__name__, e)
    if hasattr(e, "read"):
        print(e.read().decode())