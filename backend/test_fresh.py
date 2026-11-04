import requests
import json

url = 'http://127.0.0.1:8000'

# Test with a completely fresh thread ID
data = {
    'threadId': 'thread_fresh_test',
    'runId': 'run_fresh_test_1',
    'state': {
        'editorContent': '', 
        'editorOpen': True, 
        'editorLanguage': 'python',
        'sessionId': None
    },
    'messages': [],
    'tools': [],
    'context': [],
    'forwardedProps': {}
}

print("=== Fresh Test: Editor opens - should generate first question ===")
r = requests.post(url, json=data, timeout=60, stream=True)
print('Status:', r.status_code)

session_id = None
for line in r.iter_lines():
    if line:
        line = line.decode('utf-8')
        if line.startswith('data: '):
            try:
                event = json.loads(line[6:])
                print(f"Type: {event.get('type')}")
                if event.get('type') == 'TOOL_CALL_CHUNK':
                    print(f"  tool_call_name: {event.get('tool_call_name')}")
                    print(f"  delta: {event.get('delta')}")
                elif event.get('type') == 'RUN_FINISHED':
                    print(f"  State keys: {list(event.get('state', {}).keys())}")
                    print(f"  sessionId: {event.get('state', {}).get('sessionId')}")
                    istate = event.get('state', {}).get('interviewState', {})
                    print(f"  interviewState current_question_id: {istate.get('current_question_id')}")
                    print(f"  interviewState current_question: {istate.get('current_question')}")
                    print(f"  interviewState question_history: {istate.get('question_history')}")
                    if event.get('state', {}).get('sessionId'):
                        session_id = event['state']['sessionId']
            except Exception as e:
                print(f"  Parse error: {e}")

print(f"\nExtracted Session ID: {session_id}")