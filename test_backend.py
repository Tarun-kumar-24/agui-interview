import json, urllib.request

payload = {
    "threadId": "t_test",
    "runId": "r_test",
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
    with urllib.request.urlopen(req, timeout=25) as r:
        print("STATUS", r.status, r.headers.get("content-type"))
        data = r.read().decode(errors="replace")
        print(data[:3000])
except Exception as e:
    print("ERR", type(e).__name__, e)
