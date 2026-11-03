import json, urllib.request

# Test close_editor tool
payload = {
    "threadId": "t_test7",
    "runId": "r_test8",
    "state": {"editorContent": '// React TodoList component here', "editorOpen": True},
    "messages": [
        {"id": "m1", "role": "user", "content": "I want to do a React coding challenge. Please open the editor and give me a challenge."},
        {"id": "m2", "role": "assistant", "content": "I'd be happy to give you a React coding challenge! Let me open the editor and present you with a problem."},
        {"id": "m3", "role": "user", "content": "I've completed the challenge. Please close the editor and give me feedback."}
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
    with urllib.request.urlopen(req, timeout=30) as r:
        print("STATUS", r.status, r.headers.get("content-type"))
        data = r.read().decode(errors="replace")
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