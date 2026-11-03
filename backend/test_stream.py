import requests
import json

url = 'http://127.0.0.1:8000'
data = {
    'threadId': 'thread_test_early',
    'runId': 'run_test_early_2',
    'state': {'editorContent': '', 'editorOpen': False},
    'messages': [
        {'id': 'msg_1', 'role': 'user', 'content': 'Hello'},
        {'id': 'msg_2', 'role': 'assistant', 'content': 'Welcome! Tell me about your background.'},
        {'id': 'msg_3', 'role': 'user', 'content': 'I have 3 years Python experience.'},
        {'id': 'msg_4', 'role': 'assistant', 'content': 'Nice. What projects have you worked on?'},
        {'id': 'msg_5', 'role': 'user', 'content': 'I built a REST API.'},
        {'id': 'msg_6', 'role': 'assistant', 'content': 'Good. How do you handle errors?'},
        {'id': 'msg_7', 'role': 'user', 'content': 'Try-catch and logging.'},
        {'id': 'msg_8', 'role': 'user', 'content': 'Can we start the coding round?'},
        {'id': 'msg_9', 'role': 'assistant', 'content': 'Are you comfortable starting the coding round now?'},
        {'id': 'msg_10', 'role': 'user', 'content': 'Yes, let us start.'}
    ],
    'tools': [],
    'context': [],
    'forwardedProps': {}
}

r = requests.post(url, json=data, timeout=60, stream=True)
print('Status:', r.status_code)
print('Content-Type:', r.headers.get('Content-Type'))
print()

for line in r.iter_lines():
    if line:
        line = line.decode('utf-8')
        if line.startswith('data: '):
            try:
                event = json.loads(line[6:])
                print(f"Type: {event.get('type')}")
                if event.get('type') == 'TOOL_CALL_CHUNK':
                    print(f"  tool_call_id: {event.get('tool_call_id')}")
                    print(f"  tool_call_name: {event.get('tool_call_name')}")
                    print(f"  delta: {event.get('delta')}")
                elif event.get('type') == 'TEXT_MESSAGE_CHUNK':
                    print(f"  Delta: {event.get('delta')}")
                elif event.get('type') == 'RUN_FINISHED':
                    print(f"  State: {event.get('state')}")
            except Exception as e:
                print(f"  Parse error: {e}")