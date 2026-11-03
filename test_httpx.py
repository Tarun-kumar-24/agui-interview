import httpx, json

payload = {
    "model": "poolside/laguna-xs-2.1",
    "messages": [
        {
            "role": "system",
            "content": "You are an experienced technical interviewer conducting a live coding interview. Your job: 1. Ask ONE interview question at a time. Wait for the candidate's answer before asking the next. 2. Begin with a warm welcome and a brief question about their background. 3. Then move to coding questions. When you want the candidate to write code, call the open_editor tool with a description of what they should implement. The editor will open on their screen. 4. After they write code, you can read the editor content (it's sent with each message) and comment on it, suggest improvements, and ask follow-up questions. 5. When the coding exercise is done, call the close_editor tool to hide the editor and continue the interview in chat-only mode. 6. Be encouraging, professional, concise, and conversational. Current editor content (may be empty if editor is closed): console.log(\"hello\") Do not wrap your replies in markdown code fences unless you are showing a code example. Speak directly to the candidate."
        },
        {"role": "user", "content": "Hi, start the interview"}
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "open_editor",
                "description": "Open the Monaco code editor on the candidate's screen with a coding task.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Description of the coding task for the candidate."},
                        "initial_code": {"type": "string", "description": "Optional starter code to pre-fill the editor."},
                        "language": {"type": "string", "description": "Programming language for syntax highlighting (e.g., javascript, python, typescript).", "default": "javascript"}
                    },
                    "required": ["task"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "close_editor",
                "description": "Close the Monaco code editor and return to chat-only mode.",
                "parameters": {"type": "object", "properties": {}}
            }
        }
    ],
    "tool_choice": "auto",
    "stream": True,
    "temperature": 0.7,
}

headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer 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",
}

with httpx.Client(timeout=30.0) as client:
    with client.stream("POST", "https://integrate.api.nvidia.com/v1/chat/completions", json=payload, headers=headers) as response:
        print("STATUS:", response.status_code)
        if response.status_code != 200:
            print(response.read())
        else:
            for line in response.iter_lines():
                if line.startswith("data: "):
                    print(line[:200])
                    break