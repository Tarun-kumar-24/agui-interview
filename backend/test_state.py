import os
os.chdir(r'C:\Users\TARUN KANTIWAL\Documents\agui\agui-interview\backend')
from dotenv import load_dotenv
load_dotenv('.env')

from ag_ui.core import RunAgentInput, UserMessage

input_data = RunAgentInput(
    thread_id='test-thread',
    run_id='test-run',
    state={'editorContent': '', 'editorOpen': False},
    messages=[UserMessage(id='1', role='user', content='hello')],
    tools=[],
    context=[],
    forwarded_props={}
)

print('state:', input_data.state)
print('state type:', type(input_data.state))
print('messages:', input_data.messages)
print('message type:', type(input_data.messages[0]))
print('message role:', input_data.messages[0].role)
print('message content:', input_data.messages[0].content)

# Test state access
if input_data.state:
    editor_content = input_data.state.get('editorContent', '')
    print('editor_content:', editor_content)