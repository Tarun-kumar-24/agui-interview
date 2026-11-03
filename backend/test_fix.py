import sys
sys.path.insert(0, r'C:\Users\TARUN KANTIWAL\Documents\agui\agui-interview\backend')
from main import _detect_candidate_confirmation, _detect_coding_request, _update_interview_state

class MockMsg:
    def __init__(self, role, content):
        self.role = role
        self.content = content

print('=== Testing _detect_candidate_confirmation ===')
# Clear affirmative
affirmative = ['yes', 'yes please', 'yeah', 'yep', 'i agree', 'go ahead', "let's do it", 'confirm', 'absolutely', 'definitely', 'sure thing', "ok let's", 'yes, let\'s do it']
for msg in affirmative:
    msgs = [MockMsg('user', msg)]
    result = _detect_candidate_confirmation(msgs)
    print(f'  "{msg}" -> {result}')

print()
# Clear negative
negative = ['no', 'not yet', 'ask me more questions', 'continue the interview', 'let me answer more', 'later', 'decline', "don't start", 'not now', 'no thanks']
for msg in negative:
    msgs = [MockMsg('user', msg)]
    result = _detect_candidate_confirmation(msgs)
    print(f'  "{msg}" -> {result}')

print()
# Ambiguous (should return None)
ambiguous = ['please tell me more', 'start', 'okay', 'please', 'sure', 'ok', 'maybe', 'i guess']
for msg in ambiguous:
    msgs = [MockMsg('user', msg)]
    result = _detect_candidate_confirmation(msgs)
    print(f'  "{msg}" -> {result} (ambiguous)')

print()
print('=== Testing _detect_coding_request ===')
coding_requests = ['can we start coding round', 'start coding round', 'can we code', "let's code", 'coding now', 'code now', 'open editor', 'i want to start coding']
for msg in coding_requests:
    msgs = [MockMsg('user', msg)]
    result = _detect_coding_request(msgs)
    print(f'  "{msg}" -> {result}')

print()
print('=== Testing _update_interview_state flow ===')
# Turn 1: hey
msgs = [MockMsg('user', 'hey')]
state = _update_interview_state({}, msgs, None, False)
print(f'Turn 1 (hey): pending={state["coding_confirmation_pending"]}, active={state["coding_round_active"]}')

# Turn 2: can we start coding round
msgs = [MockMsg('assistant', 'Welcome! Tell me about yourself.'), MockMsg('user', 'can we start coding round')]
state = _update_interview_state({}, msgs, None, False)
print(f'Turn 2 (request coding): pending={state["coding_confirmation_pending"]}, active={state["coding_round_active"]}')

# Turn 3: yes please (confirmation was pending)
msgs = [MockMsg('assistant', 'Are you comfortable starting the coding round now?'), MockMsg('user', 'yes please')]
state = _update_interview_state({'coding_confirmation_pending': True}, msgs, None, False)
print(f'Turn 3 (confirm): pending={state["coding_confirmation_pending"]}, active={state["coding_round_active"]}')

# Turn 4: open_editor called
state = _update_interview_state({'coding_confirmation_pending': False}, msgs, 'open_editor', True)
print(f'Turn 4 (after open_editor): pending={state["coding_confirmation_pending"]}, active={state["coding_round_active"]}')

# Test decline
msgs = [MockMsg('assistant', 'Are you comfortable starting the coding round now?'), MockMsg('user', 'no, let me answer more questions')]
state = _update_interview_state({'coding_confirmation_pending': True}, msgs, None, False)
print(f'Turn 3 (decline): pending={state["coding_confirmation_pending"]}, active={state["coding_round_active"]}')

# Test ambiguous - should keep pending
msgs = [MockMsg('assistant', 'Are you comfortable starting the coding round now?'), MockMsg('user', 'please tell me more')]
state = _update_interview_state({'coding_confirmation_pending': True}, msgs, None, False)
print(f'Turn 3 (ambiguous): pending={state["coding_confirmation_pending"]}, active={state["coding_round_active"]}')