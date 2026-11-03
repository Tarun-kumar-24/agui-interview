import json, urllib.request

# Test to see if tool calls appear
payload = {
    "threadId": "t_test7",
    "runId": "r_test7",
    "state": {"editorContent": 'console.log("hello")', "editorOpen": False},
    "messages": [
        {"id": "m1", "role": "user", "content": "I want to do a React coding challenge. Please open the editor and give me a challenge."}
    ],
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
    with urllib.request.urlopen(req, timeout=60) as r:
        print("STATUS", r.status, r.headers.get("content-type"))
        data = r.read().decode(errors="replace")
        # Print all events
        for line in data.strip().split('\n\n'):
            if line.startswith('data: '):
                try:
                    event = json.loads(line[6:])
                    if event.get('type') in ['TOOL_CALL_CHUNK', 'TEXT_MESSAGE_CHUNK', 'RUN_FINISHED', 'RUN_ERROR']:
                        print(f"{event.get('type')}: {json.dumps(event)}")
                except:
                    pass
except Exception as e:
    print("ERR", type(e).__name__, e)
    if hasattr(e, "read"):
        print(e.read().decode())