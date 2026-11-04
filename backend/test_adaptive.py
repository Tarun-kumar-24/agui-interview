import requests
import json

url = 'http://127.0.0.1:8000'

# Test: Editor opens - should generate first question automatically
data = {
    'threadId': 'thread_test_adaptive',
    'runId': 'run_test_adaptive_1',
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

print("=== Test 1: Editor opens - should generate first question ===")
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
                    print(f"  State: {event.get('state')}")
                    if event.get('state', {}).get('sessionId'):
                        session_id = event['state']['sessionId']
            except Exception as e:
                print(f"  Parse error: {e}")

print(f"\nSession ID: {session_id}")

# Test 2: Send code snapshot (simulate 60-second snapshot)
if session_id:
    print("\n=== Test 2: Code snapshot with some code ===")
    data2 = {
        'threadId': 'thread_test_adaptive',
        'runId': 'run_test_adaptive_2',
        'state': {
            'editorContent': 'class Solution:\n    def solve(self, nums):\n        return len(nums)', 
            'editorOpen': True, 
            'editorLanguage': 'python',
            'sessionId': session_id
        },
        'messages': [],
        'tools': [],
        'context': [],
        'forwardedProps': {}
    }
    
    r2 = requests.post(url, json=data2, timeout=60, stream=True)
    print('Status:', r2.status_code)
    
    for line in r2.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                try:
                    event = json.loads(line[6:])
                    print(f"Type: {event.get('type')}")
                    if event.get('type') == 'TEXT_MESSAGE_CHUNK':
                        print(f"  Delta: {event.get('delta')[:100]}...")
                    elif event.get('type') == 'RUN_FINISHED':
                        print(f"  State: {event.get('state')}")
                except Exception as e:
                    print(f"  Parse error: {e}")

# Test 3: Request code review
if session_id:
    print("\n=== Test 3: Request code review ===")
    data3 = {
        'threadId': 'thread_test_adaptive',
        'runId': 'run_test_adaptive_3',
        'state': {
            'editorContent': 'class Solution:\n    def solve(self, nums):\n        return len(nums)', 
            'editorOpen': True, 
            'editorLanguage': 'python',
            'sessionId': session_id
        },
        'messages': [
            {'id': 'msg_1', 'role': 'user', 'content': "I've written the code. Can you review it?"}
        ],
        'tools': [],
        'context': [],
        'forwardedProps': {}
    }
    
    r3 = requests.post(url, json=data3, timeout=60, stream=True)
    print('Status:', r3.status_code)
    
    for line in r3.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                try:
                    event = json.loads(line[6:])
                    print(f"Type: {event.get('type')}")
                    if event.get('type') == 'TEXT_MESSAGE_CHUNK':
                        print(f"  Delta: {event.get('delta')[:100]}...")
                    elif event.get('type') == 'TOOL_CALL_CHUNK':
                        print(f"  tool_call_name: {event.get('tool_call_name')}")
                        print(f"  delta: {event.get('delta')}")
                    elif event.get('type') == 'RUN_FINISHED':
                        print(f"  State: {event.get('state')}")
                except Exception as e:
                    print(f"  Parse error: {e}")