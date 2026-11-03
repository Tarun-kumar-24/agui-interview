from ag_ui.core import RunAgentInput

payload = {
    "threadId": "thread_123",
    "runId": "run_456",
    "state": {"editorContent": 'console.log("hello")', "editorOpen": False},
    "messages": [
        {"id": "msg_1", "role": "user", "content": "Hello"}
    ],
    "tools": [],
    "context": [],
    "forwardedProps": {},
}

try:
    inp = RunAgentInput(**payload)
    print("SUCCESS!")
    print("Model dump:", inp.model_dump())
except Exception as e:
    print("ERROR:", e)