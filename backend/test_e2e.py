import requests
import json

url = 'http://127.0.0.1:8000'

def print_events(r):
    for line in r.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                try:
                    event = json.loads(line[6:])
                    print(f"  Type: {event.get('type')}")
                    if event.get('type') == 'TOOL_CALL_CHUNK':
                        print(f"  Tool: {event.get('tool_call_name')}, Delta: {event.get('delta')}")
                    elif event.get('type') == 'TEXT_MESSAGE_CHUNK':
                        print(f"  Text: {event.get('delta')[:80]}...")
                    elif event.get('type') == 'RUN_FINISHED':
                        state = event.get('state', {})
                        interview_state = state.get('interviewState', {})
                        print(f"  Session: {state.get('sessionId')}")
                        print(f"  Status: {interview_state.get('status')}")
                        print(f"  Current Q: {interview_state.get('current_question_id')}")
                        print(f"  Pending: {interview_state.get('coding_confirmation_pending')}")
                        print(f"  Active: {interview_state.get('coding_round_active')}")
                except Exception as e:
                    print(f"  Parse error: {e}")

print("=" * 60)
print("FULL INTERVIEW FLOW TEST")
print("=" * 60)

# Step 1: Start interview - theoretical questions
print("\n1. Starting interview...")
data = {
    'threadId': 'thread_e2e_test',
    'runId': 'run_1',
    'state': {'editorContent': '', 'editorOpen': False, 'editorLanguage': 'python'},
    'messages': [{'id': 'msg_1', 'role': 'user', 'content': 'Hello'}],
    'tools': [], 'context': [], 'forwardedProps': {}
}
r = requests.post(url, json=data, timeout=60, stream=True)
print_events(r)

# Step 2: Answer a few theoretical questions
print("\n2. Answering theoretical questions...")
messages = [
    {'id': 'msg_1', 'role': 'user', 'content': 'Hello'},
    {'id': 'msg_2', 'role': 'assistant', 'content': 'Welcome! Tell me about your background.'},
    {'id': 'msg_3', 'role': 'user', 'content': 'I have 3 years Python experience.'},
    {'id': 'msg_4', 'role': 'assistant', 'content': 'Nice. What projects have you worked on?'},
    {'id': 'msg_5', 'role': 'user', 'content': 'I built a REST API.'},
    {'id': 'msg_6', 'role': 'assistant', 'content': 'Good. How do you handle errors?'},
    {'id': 'msg_7', 'role': 'user', 'content': 'Try-catch and logging.'},
    {'id': 'msg_8', 'role': 'assistant', 'content': 'Great! What about testing?'},  # 4th question
    {'id': 'msg_9', 'role': 'user', 'content': 'I use pytest and unittest.'},
    {'id': 'msg_10', 'role': 'assistant', 'content': 'Nice. Can we start the coding round now?'},  # LLM asks for coding round
]

# Continue conversation to get to coding round request
data = {
    'threadId': 'thread_e2e_test',
    'runId': 'run_2',
    'state': {'editorContent': '', 'editorOpen': False, 'editorLanguage': 'python'},
    'messages': messages,
    'tools': [], 'context': [], 'forwardedProps': {}
}
r = requests.post(url, json=data, timeout=60, stream=True)
print_events(r)

# Step 3: Request coding round
print("\n3. Candidate requests coding round...")
messages.append({'id': 'msg_11', 'role': 'user', 'content': 'Can we start the coding round?'})
data = {
    'threadId': 'thread_e2e_test',
    'runId': 'run_3',
    'state': {'editorContent': '', 'editorOpen': False, 'editorLanguage': 'python'},
    'messages': messages,
    'tools': [], 'context': [], 'forwardedProps': {}
}
r = requests.post(url, json=data, timeout=60, stream=True)
print_events(r)

# Step 4: LLM asks for confirmation
print("\n4. LLM asks for confirmation...")
messages.append({'id': 'msg_12', 'role': 'assistant', 'content': 'Are you comfortable starting the coding round now?'})
data = {
    'threadId': 'thread_e2e_test',
    'runId': 'run_4',
    'state': {'editorContent': '', 'editorOpen': False, 'editorLanguage': 'python'},
    'messages': messages,
    'tools': [], 'context': [], 'forwardedProps': {}
}
r = requests.post(url, json=data, timeout=60, stream=True)
print_events(r)

# Step 5: Candidate confirms
print("\n5. Candidate confirms...")
messages.append({'id': 'msg_13', 'role': 'user', 'content': 'Yes, let us start.'})
data = {
    'threadId': 'thread_e2e_test',
    'runId': 'run_5',
    'state': {'editorContent': '', 'editorOpen': False, 'editorLanguage': 'python'},
    'messages': messages,
    'tools': [], 'context': [], 'forwardedProps': {}
}
r = requests.post(url, json=data, timeout=60, stream=True)
print_events(r)

# Step 6: Frontend confirms editor open
print("\n6. Frontend confirms editor open...")
messages.append({'id': 'msg_14', 'role': 'assistant', 'content': 'Starting coding round...'})
data = {
    'threadId': 'thread_e2e_test',
    'runId': 'run_6',
    'state': {'editorContent': '', 'editorOpen': True, 'editorLanguage': 'python'},
    'messages': messages,
    'tools': [], 'context': [], 'forwardedProps': {}
}
r = requests.post(url, json=data, timeout=60, stream=True)
print_events(r)

# Step 7: Candidate writes code and requests review
print("\n7. Candidate writes code and requests review...")
messages.append({'id': 'msg_15', 'role': 'user', 'content': "I've written the code. Can you review it?"})
data = {
    'threadId': 'thread_e2e_test',
    'runId': 'run_7',
    'state': {'editorContent': 'def solve(nums):\n    return max(nums)', 'editorOpen': True, 'editorLanguage': 'python'},
    'messages': messages,
    'tools': [], 'context': [], 'forwardedProps': {}
}
r = requests.post(url, json=data, timeout=60, stream=True)
print_events(r)

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)