import json, urllib.request

# Continue the conversation - the agent should call open_editor
payload = {
    "threadId": "t_test5",
    "runId": "r_test6",
    "state": {"editorContent": 'console.log("hello")', "editorOpen": False},
    "messages": [
        {"id": "m1", "role": "user", "content": "Hi, I want to do a coding challenge"},
        {"id": "m2", "role": "assistant", "content": "Hi there! I'm excited to help you with a coding challenge. First, let me ask you a bit about your background: What's your current role and which programming languages do you feel most comfortable with? Also, what type of coding challenge interests you most?"},
        {"id": "m3", "role": "user", "content": "I'm a frontend developer, I know JavaScript and React. I'd like to do a React component challenge."}
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
        print(data[:8000])
except Exception as e:
    print("ERR", type(e).__name__, e)
    if hasattr(e, "read"):
        print(e.read().decode())