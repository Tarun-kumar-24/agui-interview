import requests
import json

url = 'http://127.0.0.1:8000'
data = {
    'threadId': 'test-thread-2',
    'runId': 'test-run-2',
    'state': {'editorContent': '', 'editorOpen': False},
    'messages': [{'id': '1', 'role': 'user', 'content': 'I want to do a coding challenge'}],
    'tools': [],
    'context': [],
    'forwardedProps': {'editorContent': 'def hello():\n    print("world")', 'editorOpen': True}
}

r = requests.post(url, json=data, timeout=30)
print('Status:', r.status_code)
print('Response (first 1500 chars):', r.text[:1500])