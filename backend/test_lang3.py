import requests
import json

url = 'http://127.0.0.1:8000'
# Test sending a message with editorLanguage in state
data = {
    'threadId': 'thread_test_lang3',
    'runId': 'run_test_lang3',
    'state': {
        'editorContent': 'class Solution:\n    def solve(self, nums):\n        return len(nums)',
        'editorOpen': True,
        'editorLanguage': 'python',
        'interviewState': {'questions_asked': 2, 'coding_confirmation_pending': False, 'coding_round_active': True}
    },
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
        {'id': 'msg_10', 'role': 'user', 'content': 'Yes, let us start.'},
        {'id': 'msg_11', 'role': 'assistant', 'content': 'Here is your coding task...'},
        {'id': 'msg_12', 'role': 'user', 'content': 'I have written the solution'}
    ],
    'tools': [],
    'context': [],
    'forwardedProps': {}
}

r = requests.post(url, json=data, timeout=60, stream=True)
print('Status:', r.status_code)

for line in r.iter_lines():
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