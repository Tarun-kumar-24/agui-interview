with open(r'C:\Users\TARUN KANTIWAL\Documents\agui\agui-interview\backend\main.py', 'r') as f:
    content = f.read()

lines = content.splitlines(keepends=True)

start_idx = None
for i, line in enumerate(lines):
    if '@app.post("/")' in line:
        start_idx = i
        break

if start_idx is None:
    print('Could not find endpoint')
else:
    end_idx = None
    for i in range(start_idx + 1, len(lines)):
        if lines[i].startswith('@app.') or lines[i].startswith('if __name__'):
            end_idx = i
            break

    if end_idx is None:
        end_idx = len(lines)

    # Replace the endpoint
    new_endpoint = '''@app.post("/")
async def run_agent(request: Request):
    # Parse raw JSON to fix missing message IDs before Pydantic validation
    body = await request.json()

    # Ensure all messages have an 'id' field (required by UserMessage/AssistantMessage schemas)
    if "messages" in body and isinstance(body["messages"], list):
        for msg in body["messages"]:
            if isinstance(msg, dict) and ("id" not in msg or not msg["id"]):
                msg["id"] = f"msg_{uuid.uuid4().hex[:8]}"

    # Now validate with RunAgentInput
    input_data = RunAgentInput(**body)

    thread_id = input_data.thread_id
    run_id = input_data.run_id
    editor_content = _get_editor_content(input_data)
    editor_open = _get_editor_open(input_data)

    # Build system prompt with editor state
    sys_prompt = SYSTEM_PROMPT.format(editor_content=editor_content if editor_open else "(editor is closed)")

    messages = [{"role": "system", "content": sys_prompt}]
    for msg in input_data.messages or []:
        role = getattr(msg, "role", "user")
        content = getattr(msg, "content", "") or ""
        messages.append({"role": role, "content": content})

    event_encoder = EventEncoder()

    async def event_generator() -> AsyncGenerator[bytes, None]:
        message_id = f"msg_{run_id}"

        yield event_encoder.encode(
            RunStartedEvent(
                type=EventType.RUN_STARTED,
                thread_id=thread_id,
                run_id=run_id,
                input=input_data,
            )
        )

        payload = {
            "model": OPENAI_MODEL,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
        }

        if EDITOR_TOOLS:
            payload["tools"] = EDITOR_TOOLS
            payload["tool_choice"] = "auto"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
        }

        async with http_client.stream(
            "POST",
            f"{OPENAI_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
        ) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                raise Exception(f"API error {response.status_code}: {error_text.decode()}")

            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                if line == "data: [DONE]":
                    break
                try:
                    chunk_data = json.loads(line[6:])
                    choices = chunk_data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield event_encoder.encode(
                            TextMessageChunkEvent(
                                type=EventType.TEXT_MESSAGE_CHUNK,
                                message_id=message_id,
                                role="assistant",
                                delta=content,
                            )
                        )
                    tool_calls = delta.get("tool_calls", [])
                    for tool_call in tool_calls:
                        fn = tool_call.get("function", {})
                        yield event_encoder.encode(
                            ToolCallChunkEvent(
                                type=EventType.TOOL_CALL_CHUNK,
                                tool_call_id=tool_call.get("id"),
                                tool_call_name=fn.get("name"),
                                parent_message_id=message_id,
                                delta=fn.get("arguments"),
                            )
                        )
                except json.JSONDecodeError:
                    continue

        yield event_encoder.encode(
            RunFinishedEvent(
                type=EventType.RUN_FINISHED,
                thread_id=thread_id,
                run_id=run_id,
            )
        )

    return StreamingResponse(
        event_generator(),
        media_type=event_encoder.get_content_type(),
    )

'''
    # Replace lines start_idx to end_idx
    new_lines = lines[:start_idx] + [new_endpoint] + lines[end_idx:]
    
    with open(r'C:\Users\TARUN KANTIWAL\Documents\agui\agui-interview\backend\main.py', 'w') as f:
        f.write(''.join(new_lines))
    
    print('Endpoint replaced successfully')