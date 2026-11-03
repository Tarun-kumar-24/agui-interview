import os
from typing import AsyncGenerator
import json
import httpx
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from ag_ui.core import (
    EventType,
    RunStartedEvent,
    RunFinishedEvent,
    RunErrorEvent,
    TextMessageChunkEvent,
    ToolCallChunkEvent,
    RunAgentInput,
)
from ag_ui.encoder import EventEncoder

# Load .env from the backend directory explicitly
backend_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(backend_dir, ".env")
load_dotenv(env_path)

# Create a shared httpx client
http_client = httpx.AsyncClient(timeout=60.0)

app = FastAPI(title="AG-UI Interview Agent")

# Debug middleware to log raw request body
@app.middleware("http")
async def log_request_body(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/":
        body = await request.body()
        print(f"=== RAW REQUEST ===")
        print(body.decode())
        print(f"===================")
    response = await call_next(request)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """You are a professional technical interviewer.

1. Start with a warm welcome and ask about the candidate's background.
2. Ask one question at a time and wait for the answer.
3. Ask around 5–6 meaningful interview questions before considering the coding round.
4. When ready, ask: "Are you comfortable starting the coding round now?"
5. If the candidate requests an early coding round, ask the same confirmation question.
6. Only after explicit confirmation, announce the coding round and immediately call `open_editor` with a coding task. Never describe the task in chat.
7. If the candidate declines, continue the interview.
8. Prevent duplicate confirmations and tool calls.
9. During coding, review the editor content and ask relevant follow-up questions.
10. When coding is complete, call `close_editor`.

Interview state (follow this on every turn):
- questions_asked: {questions_asked}
- coding_confirmation_pending: {coding_confirmation_pending}
- coding_round_active: {coding_round_active}

Never open the editor without explicit confirmation.

Current editor content:
{editor_content}

Keep replies short, natural, and conversational. Do not use markdown code fences unless showing code."""

# Tools the agent can call to control the editor (OpenAI format)
EDITOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_editor",
            "description": "Open the Monaco code editor on the candidate's screen with a coding task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Description of the coding task for the candidate.",
                    },
                    "initial_code": {
                        "type": "string",
                        "description": "Optional starter code to pre-fill the editor.",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language for syntax highlighting (e.g., javascript, python, typescript).",
                        "default": "javascript",
                    },
                },
                "required": ["task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_editor",
            "description": "Close the Monaco code editor and return to chat-only mode.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


def _get_editor_content(input_data: RunAgentInput) -> str:
    content = ""
    if input_data.state and isinstance(input_data.state, dict):
        content = input_data.state.get("editorContent", "") or ""
    if not content and input_data.forwarded_props and isinstance(input_data.forwarded_props, dict):
        content = input_data.forwarded_props.get("editorContent", "") or ""
    return content


def _get_editor_open(input_data: RunAgentInput) -> bool:
    if input_data.state and isinstance(input_data.state, dict):
        val = input_data.state.get("editorOpen", False)
        return bool(val) if isinstance(val, bool) else val.lower() == "true"
    if input_data.forwarded_props and isinstance(input_data.forwarded_props, dict):
        val = input_data.forwarded_props.get("editorOpen", False)
        return bool(val) if isinstance(val, bool) else val.lower() == "true"
    return False


def _get_interview_state(input_data: RunAgentInput) -> dict:
    """Extract interview state from input data."""
    state = {}
    if input_data.state and isinstance(input_data.state, dict):
        state = input_data.state.get("interviewState", {}) or {}
    if not state and input_data.forwarded_props and isinstance(input_data.forwarded_props, dict):
        state = input_data.forwarded_props.get("interviewState", {}) or {}
    return state


def _count_questions_asked(messages: list) -> int:
    """Count substantive interview questions asked by the assistant."""
    count = 0
    for msg in messages:
        role = getattr(msg, "role", "")
        content = getattr(msg, "content", "") or ""
        if role == "assistant" and content:
            content_lower = content.lower().strip()
            if any(skip in content_lower for skip in [
                "welcome", "hello", "hi there", "nice to meet",
                "are you comfortable starting the coding round",
                "coding round", "open_editor", "let's begin", "let's start"
            ]):
                continue
            if "?" in content or any(q in content_lower for q in [
                "tell me about", "describe", "explain", "how would you",
                "what is", "what are", "why do", "can you", "could you"
            ]):
                count += 1
    return count


def _detect_confirmation_question(messages: list) -> bool:
    """Check if the confirmation question was asked in the last assistant message."""
    for msg in reversed(messages):
        role = getattr(msg, "role", "")
        content = getattr(msg, "content", "") or ""
        if role == "assistant":
            content_lower = content.lower().strip()
            if "are you comfortable starting the coding round now" in content_lower:
                return True
            break
    return False


def _detect_candidate_confirmation(messages: list) -> str | None:
    """Check if candidate confirmed or declined in the last user message.
    
    Only accepts clear affirmative/negative responses. Generic words like
    'please', 'start', 'okay' alone are not treated as confirmation.
    """
    for msg in reversed(messages):
        role = getattr(msg, "role", "")
        content = getattr(msg, "content", "") or ""
        if role == "user":
            content_lower = content.lower().strip()
            # Clear affirmative patterns - must be primarily affirmative
            affirmative_patterns = [
                "yes please", "yes, please", "yeah", "yep", "i agree", 
                "go ahead", "let's do it", "lets do it", "confirm", "absolutely",
                "definitely", "sure thing", "ok let's", "ok, let's"
            ]
            # Check for "yes" as a clear standalone or at start
            if content_lower == "yes" or content_lower.startswith("yes ") or content_lower.startswith("yes,"):
                return "confirmed"
            if any(pattern in content_lower for pattern in affirmative_patterns):
                return "confirmed"
            
            # Clear negative patterns
            negative_patterns = [
                "not yet", "ask me more", "more questions", "continue the interview",
                "continue interview", "let me answer", "later", "decline",
                "don't start", "do not start", "not now", "no thanks"
            ]
            if content_lower == "no" or content_lower.startswith("no ") or content_lower.startswith("no,"):
                return "declined"
            if any(pattern in content_lower for pattern in negative_patterns):
                return "declined"
            
            # Ambiguous - keep pending, will re-ask
            break
    return None


def _detect_coding_request(messages: list) -> bool:
    """Check if candidate explicitly requested coding round in the last user message."""
    for msg in reversed(messages):
        role = getattr(msg, "role", "")
        content = getattr(msg, "content", "") or ""
        if role == "user":
            content_lower = content.lower().strip()
            if any(phrase in content_lower for phrase in [
                "coding round", "start coding", "can we code", "let's code", "lets code",
                "coding now", "code now", "open editor", "editor"
            ]):
                return True
            break
    return False


def _update_interview_state(input_state: dict, messages: list, tool_called: str | None, editor_open: bool) -> dict:
    """Update interview state based on conversation and tool calls."""
    state = dict(input_state)
    
    state.setdefault("questions_asked", 0)
    state.setdefault("coding_confirmation_pending", False)
    state.setdefault("coding_round_active", False)
    
    # Update coding_round_active based on editor state
    state["coding_round_active"] = editor_open
    
    # Count questions from conversation (only if not in coding round)
    if not state["coding_round_active"]:
        state["questions_asked"] = _count_questions_asked(messages)
    
    # Handle confirmation flow
    if state["coding_confirmation_pending"]:
        candidate_response = _detect_candidate_confirmation(messages)
        if candidate_response == "confirmed":
            state["coding_confirmation_pending"] = False
        elif candidate_response == "declined":
            state["coding_confirmation_pending"] = False
        # If ambiguous (None), keep pending - will re-ask
    else:
        # Check if confirmation question was just asked (but not if we just called a tool)
        if tool_called is None and _detect_confirmation_question(messages):
            state["coding_confirmation_pending"] = True
        # Check if user explicitly requested coding round (and not already pending/active)
        elif tool_called is None and not state["coding_round_active"]:
            if _detect_coding_request(messages):
                state["coding_confirmation_pending"] = True
    
    # Handle tool calls (after confirmation flow so tool calls take precedence)
    if tool_called == "open_editor":
        state["coding_round_active"] = True
        state["coding_confirmation_pending"] = False
    elif tool_called == "close_editor":
        state["coding_round_active"] = False
    
    return state


@app.post("/")
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
    
    # Get and update interview state
    incoming_interview_state = _get_interview_state(input_data)
    interview_state = _update_interview_state(incoming_interview_state, input_data.messages or [], None, editor_open)
    
    # Track whether this turn was a confirmation request/response
    was_pending = incoming_interview_state.get("coding_confirmation_pending", False)
    now_pending = interview_state.get("coding_confirmation_pending", False)
    coding_round_active = interview_state.get("coding_round_active", False)

    # Build system prompt with editor state and interview state
    sys_prompt = SYSTEM_PROMPT.format(
        editor_content=editor_content if editor_open else "(editor is closed)",
        questions_asked=interview_state.get("questions_asked", 0),
        coding_confirmation_pending=interview_state.get("coding_confirmation_pending", False),
        coding_round_active=interview_state.get("coding_round_active", False),
    )

    messages = [{"role": "system", "content": sys_prompt}]
    for msg in input_data.messages or []:
        role = getattr(msg, "role", "user")
        content = getattr(msg, "content", "") or ""
        messages.append({"role": role, "content": content})

    event_encoder = EventEncoder()

    # CASE 1: User just requested coding round (pending transitioned False -> True)
    # Return confirmation question immediately without calling LLM
    if not was_pending and now_pending and not coding_round_active:
        async def confirmation_event_generator() -> AsyncGenerator[bytes, None]:
            message_id = f"msg_{run_id}"
            
            yield event_encoder.encode(
                RunStartedEvent(
                    type=EventType.RUN_STARTED,
                    thread_id=thread_id,
                    run_id=run_id,
                    input=input_data,
                )
            )
            
            # Stream the exact confirmation question
            confirmation_text = "Are you comfortable starting the coding round now?"
            yield event_encoder.encode(
                TextMessageChunkEvent(
                    type=EventType.TEXT_MESSAGE_CHUNK,
                    message_id=message_id,
                    role="assistant",
                    delta=confirmation_text,
                )
            )
            
            # Return updated state with pending=True
            yield event_encoder.encode(
                RunFinishedEvent(
                    type=EventType.RUN_FINISHED,
                    thread_id=thread_id,
                    run_id=run_id,
                    state={"interviewState": interview_state},
                )
            )
        
        return StreamingResponse(
            confirmation_event_generator(),
            media_type=event_encoder.get_content_type(),
        )

    # CASE 2: User responded to pending confirmation (pending transitioned True -> False)
    # Determine if confirmed or declined to decide whether to allow open_editor tool
    allow_editor_tool = False
    if was_pending and not now_pending and not coding_round_active:
        # Check the latest user message for clear confirmation
        candidate_response = _detect_candidate_confirmation(input_data.messages or [])
        if candidate_response == "confirmed":
            allow_editor_tool = True

    async def event_generator() -> AsyncGenerator[bytes, None]:
        message_id = f"msg_{run_id}"
        tool_called = None
        tool_call_buffer = {}
        open_editor_authorized = allow_editor_tool  # Track if open_editor is allowed this turn

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

        # Only provide editor tools if explicitly authorized (confirmed) or already in coding round
        if EDITOR_TOOLS and (open_editor_authorized or coding_round_active):
            payload["tools"] = EDITOR_TOOLS
            payload["tool_choice"] = "auto"
        elif EDITOR_TOOLS:
            # Tools available but open_editor not authorized - provide tools but we'll guard
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
                        tc_id = tool_call.get("id")
                        tool_name = fn.get("name")
                        if tool_name:
                            tool_called = tool_name
                        
                        # ENFORCEMENT GUARD: Block open_editor if not authorized this turn
                        if tool_name == "open_editor" and not open_editor_authorized and not coding_round_active:
                            # Suppress the tool call - don't forward to frontend
                            continue
                        
                        yield event_encoder.encode(
                            ToolCallChunkEvent(
                                type=EventType.TOOL_CALL_CHUNK,
                                tool_call_id=tc_id,
                                tool_call_name=fn.get("name"),
                                parent_message_id=message_id,
                                delta=fn.get("arguments"),
                            )
                        )
                except json.JSONDecodeError:
                    continue

        # Update interview state with tool call info
        updated_state = _update_interview_state(interview_state, input_data.messages or [], tool_called, editor_open)
        
        # Include updated state in RunFinishedEvent
        yield event_encoder.encode(
            RunFinishedEvent(
                type=EventType.RUN_FINISHED,
                thread_id=thread_id,
                run_id=run_id,
                state={"interviewState": updated_state},
            )
        )

    return StreamingResponse(
        event_generator(),
        media_type=event_encoder.get_content_type(),
    )

@app.on_event("shutdown")
async def shutdown_event():
    await http_client.aclose()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)