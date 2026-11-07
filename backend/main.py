import asyncio
import base64
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

import httpx
import edge_tts
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ag_ui.core import (
    EventType,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StateSnapshotEvent,
    TextMessageChunkEvent,
    ToolCallChunkEvent,
)
from ag_ui.encoder import EventEncoder

from interview_session import (
    CodeSnapshot,
    InterviewStatus,
    Question,
    create_llm_decision_prompt,
    parse_llm_decision,
    session_manager,
)


backend_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(backend_dir, ".env"))

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_MODELS = (
    [
        model.strip()
        for model in os.getenv("OPENAI_MODELS", OPENAI_MODEL).split(",")
        if model.strip()
    ]
    or [OPENAI_MODEL]
)
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "en-US-AndrewMultilingualNeural")
EDGE_TTS_RATE = os.getenv("EDGE_TTS_RATE", "+8%")
EDGE_TTS_VOLUME = os.getenv("EDGE_TTS_VOLUME", "+0%")

EDGE_TTS_VOICES = {
    "en-US-AndrewMultilingualNeural",
    "en-US-AvaMultilingualNeural",
    "en-US-BrianMultilingualNeural",
    "en-US-EmmaMultilingualNeural",
}


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=800)
    voice: Optional[str] = None

http_client = httpx.AsyncClient(timeout=60.0)
session_locks: dict[str, asyncio.Lock] = {}
tts_semaphore = asyncio.Semaphore(4)
app = FastAPI(title="AG-UI Interview Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# These schemas remain the public AG-UI tool contract. The backend executes
# interview decisions explicitly so fragmented provider tool calls cannot race.
INTERVIEW_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_editor",
            "description": "Open or update Monaco with the active coding task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "initial_code": {"type": "string"},
                    "language": {"type": "string"},
                    "question_id": {"type": "string"},
                    "question_revision": {"type": "integer"},
                    "replace_code": {"type": "boolean"},
                },
                "required": ["task", "language", "question_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_editor",
            "description": "Hide Monaco after a submission or close it when coding ends.",
            "parameters": {
                "type": "object",
                "properties": {
                    "end_interview": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_code_snapshot",
            "description": "Record the latest editor state for adaptive analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "code": {"type": "string"},
                    "language": {"type": "string"},
                },
                "required": ["session_id", "code", "language"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_code_review",
            "description": "Review the latest complete editor state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "code": {"type": "string"},
                    "language": {"type": "string"},
                },
                "required": ["session_id", "code", "language"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "end_interview",
            "description": "End the adaptive coding interview.",
            "parameters": {
                "type": "object",
                "properties": {"session_id": {"type": "string"}},
                "required": ["session_id"],
            },
        },
    },
]


SYSTEM_PROMPT = """You are an adaptive technical interviewer conducting a live interview.

INTERVIEW FLOW:
1. Start warmly and ask one theoretical question at a time.
2. Ask at least 6 meaningful theoretical questions before suggesting coding.
3. When ready, ask exactly: "Are you comfortable starting the coding round now?"
4. If the candidate requests coding early, the application will handle confirmation.
5. Do not invent a coding task in chat. The application places coding tasks in Monaco.
6. If the candidate declines coding, continue the theoretical interview naturally.

BEHAVIOR:
- Be concise, natural, and conversational.
- Adapt theoretical questions to previous answers.
- Never reveal complete solutions.
- Do not claim to have executed code.
- The backend, not you, controls editor state and coding task transitions.

CURRENT STATE:
- Theoretical questions asked: {questions_asked}
- Coding confirmation pending: {confirmation_pending}
- Interview status: {status}
- Selected language: {language}
"""


def _model_request_fields(require_parameters: bool = False) -> dict:
    """Use OpenRouter's cross-model failover while retaining generic OpenAI compatibility."""
    if "openrouter.ai" not in OPENAI_BASE_URL or len(OPENAI_MODELS) == 1:
        return {"model": OPENAI_MODELS[0]}

    provider = {
        "allow_fallbacks": True,
        "sort": {"by": "latency", "partition": "none"},
    }
    if require_parameters:
        provider["require_parameters"] = True
    return {
        "models": OPENAI_MODELS,
        "provider": provider,
    }


def _message_value(message, field: str, default=""):
    if isinstance(message, dict):
        return message.get(field, default)
    return getattr(message, field, default)


def _count_questions_asked(messages: list) -> int:
    count = 0
    for message in messages:
        role = _message_value(message, "role")
        content = (_message_value(message, "content") or "").strip()
        lowered = content.lower()
        if role != "assistant" or not content:
            continue
        if "are you comfortable starting the coding round" in lowered:
            continue
        if "?" in content or any(
            phrase in lowered
            for phrase in ("tell me about", "describe", "explain", "how would you", "what is", "why")
        ):
            count += 1
    return count


def _detect_confirmation_question(messages: list) -> bool:
    for message in reversed(messages):
        if _message_value(message, "role") == "assistant":
            content = (_message_value(message, "content") or "").lower()
            return "are you comfortable starting the coding round now" in content
    return False


def _detect_candidate_confirmation(messages: list) -> Optional[str]:
    content = _latest_user_message(messages).lower().strip()
    if not content:
        return None

    negative_patterns = (
        r"\bnot\s+(ready|yet|now)\b",
        r"\b(no|nope|decline)\b",
        r"\b(don't|do not)\s+start\b",
        r"\bask me more\b",
        r"\bcontinue (the )?interview\b",
    )
    if any(re.search(pattern, content) for pattern in negative_patterns):
        return "declined"

    affirmative_patterns = (
        r"\b(yes|yeah|yep|absolutely|definitely|confirmed)\b",
        r"\b(go ahead|let's do it|lets do it|i am ready|i'm ready|ready to start)\b",
    )
    if any(re.search(pattern, content) for pattern in affirmative_patterns):
        return "confirmed"
    return None


def _detect_coding_request(messages: list) -> bool:
    content = _latest_user_message(messages).lower()
    return any(
        phrase in content
        for phrase in (
            "coding round",
            "start coding",
            "can we code",
            "let's code",
            "lets code",
            "code now",
            "open editor",
        )
    )


def _detect_completion_claim(messages: list) -> bool:
    content = _latest_user_message(messages).lower().strip()
    if not content or re.search(r"\b(not done|not complete|haven't completed|have not completed)\b", content):
        return False
    return any(
        re.search(pattern, content)
        for pattern in (
            r"\bi(?:'m| am)?\s+(?:done|finished|complete)\b",
            r"\bi have complete(?:d)?(?:\s+(?:this|it|the solution))?\b",
            r"\b(?:this|it|the solution) is (?:done|finished|complete)\b",
            r"\bfinished (?:this|it|the solution)\b",
        )
    )


def _latest_user_message(messages: list) -> str:
    for message in reversed(messages):
        if _message_value(message, "role") == "user":
            return _message_value(message, "content") or ""
    return ""


def _get_state_value(input_data: RunAgentInput, key: str, default=None):
    if input_data.state and isinstance(input_data.state, dict) and key in input_data.state:
        return input_data.state.get(key)
    if input_data.forwarded_props and isinstance(input_data.forwarded_props, dict):
        return input_data.forwarded_props.get(key, default)
    return default


def _get_editor_content(input_data: RunAgentInput) -> str:
    return _get_state_value(input_data, "editorContent", "") or ""


def _get_editor_open(input_data: RunAgentInput) -> bool:
    value = _get_state_value(input_data, "editorOpen", False)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)


def _get_editor_language(input_data: RunAgentInput) -> str:
    return _get_state_value(input_data, "editorLanguage", "python") or "python"


def _get_session_id(input_data: RunAgentInput) -> Optional[str]:
    return _get_state_value(input_data, "sessionId")


def _get_request_type(input_data: RunAgentInput) -> str:
    request_type = _get_state_value(input_data, "requestType", "chat")
    return request_type if request_type in {"chat", "snapshot", "inactivity", "review"} else "chat"


def _get_question_id(input_data: RunAgentInput) -> Optional[str]:
    return _get_state_value(input_data, "questionId")


def _update_interview_state(input_state: dict, messages: list, tool_called: Optional[str], editor_open: bool) -> dict:
    """Compatibility helper for older diagnostics; server sessions are authoritative."""
    state = dict(input_state or {})
    state["questions_asked"] = max(state.get("questions_asked", 0), _count_questions_asked(messages))
    state.setdefault("coding_confirmation_pending", False)
    state["coding_round_active"] = bool(editor_open)
    if tool_called == "open_editor":
        state["coding_round_active"] = True
        state["coding_confirmation_pending"] = False
    elif tool_called == "close_editor":
        state["coding_round_active"] = False
    return state


def _extract_json_object(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("LLM response did not contain a JSON object")
    return json.loads(text[start:end])


async def _json_completion(prompt: str, temperature: float) -> dict:
    payload = {
        **_model_request_fields(require_parameters=True),
        "messages": [{"role": "system", "content": prompt}],
        "stream": False,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    response = await http_client.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        json=payload,
        headers=headers,
    )
    response.raise_for_status()
    response_data = response.json()
    choices = response_data.get("choices", [])
    if not choices:
        raise ValueError("LLM response contained no choices")
    content = choices[0].get("message", {}).get("content", "")
    return _extract_json_object(content)


def _default_decision(reason: str) -> dict:
    return {
        "action": "WAIT_FOR_CANDIDATE",
        "reason": reason,
        "message": "",
        "candidate_intent": "other",
        "question_disposition": "continue",
        "assessment_complete": False,
        "updated_question_text": None,
        "next_question": None,
        "evaluation": None,
    }


async def call_llm_for_decision(session_id: str, trigger: str, extra_context: str = "") -> dict:
    session = session_manager.get_session(session_id)
    if not session:
        return _default_decision("Session not found")

    prompt = create_llm_decision_prompt(session, trigger, extra_context)
    try:
        data = await _json_completion(prompt, temperature=0.3)
        parsed = _default_decision("LLM decision")
        parsed.update(data)
        return parsed
    except Exception as error:
        print(f"LLM decision failed: {error}")
        return _default_decision(f"Decision error: {error}")


def _question_from_data(data: dict, language: str) -> Optional[Question]:
    if not isinstance(data, dict) or not str(data.get("question_text", "")).strip():
        return None
    try:
        estimated_minutes = int(data.get("estimated_minutes") or 3)
    except (TypeError, ValueError):
        estimated_minutes = 3
    difficulty = str(data.get("difficulty") or "easy").lower()
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "easy"
    return Question(
        question_id=f"q_{uuid.uuid4().hex[:8]}",
        question_text=str(data["question_text"]).strip(),
        concept=str(data.get("concept") or "general programming"),
        difficulty=difficulty,
        estimated_minutes=max(1, min(estimated_minutes, 30)),
        generated_at=datetime.now(timezone.utc).isoformat(),
        starter_code=str(data.get("starter_code") or ""),
        language=language,
    )


async def generate_question_llm(
    session_id: str,
    previous_context: str = "",
    language: Optional[str] = None,
) -> Optional[Question]:
    session = session_manager.get_session(session_id)
    if not session:
        return None

    selected_language = language or session.selected_language or "python"
    history = [
        {
            "question": question.question_text,
            "concept": question.concept,
            "difficulty": question.difficulty,
            "outcome": question.completion_reason,
            "review": question.review_result,
        }
        for question in session.question_history[-5:]
    ]
    prompt = f"""You generate the next task for an adaptive live coding interview.

Selected programming language: {selected_language}
Questions attempted: {session.total_questions_attempted}
Question history: {json.dumps(history)}
Candidate strengths: {json.dumps(session.candidate_strengths)}
Candidate weaknesses: {json.dumps(session.candidate_weaknesses)}
Latest actual editor code: {session.last_code_content[:4000] or "(empty)"}
Additional context: {previous_context}

Generate one small, focused 3-4 minute task. Adapt difficulty from demonstrated performance,
avoid repeating concepts, and build on prior work only when useful. The starter code must use
{selected_language}. Do not put the task description or question comments in starter_code.

Return only JSON:
{{
  "question_text": "Complete task wording, requirements, and a short example",
  "concept": "primary concept",
  "difficulty": "easy|medium|hard",
  "estimated_minutes": 3,
  "starter_code": "Optional signature or minimal scaffold only"
}}"""
    try:
        data = await _json_completion(prompt, temperature=0.4)
        return _question_from_data(data, selected_language)
    except Exception as error:
        print(f"Question generation failed: {error}")
        return None


async def review_code_llm(session_id: str, code: str, language: str) -> dict:
    session = session_manager.get_session(session_id)
    if not session or not session.current_question:
        return {
            "correctness": "insufficient",
            "concept_understanding": "insufficient",
            "issues": ["No active question"],
            "feedback": "There is no active coding question to review.",
        }

    prompt = f"""You are reviewing the latest actual editor code in a live coding interview.

QUESTION:
{session.current_question.question_text}

CONCEPT: {session.current_question.concept}
DIFFICULTY: {session.current_question.difficulty}
LANGUAGE: {language}

LATEST CANDIDATE CODE:
{code or "(empty)"}

Evaluate only the code above against the active question. Do not assume an earlier snapshot and
do not provide a complete solution. Return only JSON:
{{
  "correctness": "acceptable|partial|incorrect",
  "concept_understanding": "good|developing|insufficient",
  "issues": ["specific issue"],
  "feedback": "Concise, constructive feedback without the full solution"
}}"""
    try:
        return await _json_completion(prompt, temperature=0.3)
    except Exception as error:
        print(f"Code review failed: {error}")
        return {
            "correctness": "error",
            "concept_understanding": "insufficient",
            "issues": [str(error)],
            "feedback": "I could not complete the review. Please try again.",
        }


async def generate_casual_prompt_llm(session_id: str) -> str:
    decision = await call_llm_for_decision(
        session_id,
        "INACTIVITY",
        "The candidate has been inactive. Give one brief, non-solution check-in or return WAIT_FOR_CANDIDATE.",
    )
    return decision.get("message") or ""


def _state_payload(session) -> dict:
    return {
        "interviewState": session_manager.to_dict(session),
        "sessionId": session.session_id,
    }


def _editor_tool(
    question: Question,
    session,
    replace_code: bool,
    initial_code: Optional[str] = None,
) -> tuple[str, dict]:
    return (
        "open_editor",
        {
            "task": question.question_text,
            "initial_code": question.starter_code if initial_code is None else initial_code,
            "language": question.language or session.selected_language,
            "question_id": question.question_id,
            "question_revision": session.question_revision,
            "concept": question.concept,
            "difficulty": question.difficulty,
            "replace_code": replace_code,
        },
    )


def _event_response(
    input_data: RunAgentInput,
    session,
    text: str = "",
    tools: Optional[list[tuple[str, dict]]] = None,
    error: Optional[str] = None,
) -> StreamingResponse:
    encoder = EventEncoder()
    tools = tools or []
    final_state = _state_payload(session)

    async def event_generator() -> AsyncGenerator[bytes, None]:
        message_id = f"msg_{input_data.run_id}"
        yield encoder.encode(
            RunStartedEvent(
                type=EventType.RUN_STARTED,
                thread_id=input_data.thread_id,
                run_id=input_data.run_id,
                input=input_data,
            )
        )
        if text:
            yield encoder.encode(
                TextMessageChunkEvent(
                    type=EventType.TEXT_MESSAGE_CHUNK,
                    message_id=message_id,
                    role="assistant",
                    delta=text,
                )
            )
        for name, arguments in tools:
            yield encoder.encode(
                ToolCallChunkEvent(
                    type=EventType.TOOL_CALL_CHUNK,
                    tool_call_id=f"tc_{uuid.uuid4().hex[:8]}",
                    tool_call_name=name,
                    parent_message_id=message_id,
                    delta=json.dumps(arguments),
                )
            )
        if error:
            yield encoder.encode(
                RunErrorEvent(type=EventType.RUN_ERROR, message=error, code="AGENT_ERROR")
            )
            return
        yield encoder.encode(
            StateSnapshotEvent(
                type=EventType.STATE_SNAPSHOT,
                snapshot=final_state,
            )
        )
        yield encoder.encode(
            RunFinishedEvent(
                type=EventType.RUN_FINISHED,
                thread_id=input_data.thread_id,
                run_id=input_data.run_id,
            )
        )

    return StreamingResponse(event_generator(), media_type=encoder.get_content_type())


def _question_conflict(input_data: RunAgentInput, session) -> bool:
    expected_question_id = _get_question_id(input_data)
    expected_revision = _get_state_value(input_data, "questionRevision")
    id_conflict = bool(expected_question_id and expected_question_id != session.current_question_id)
    revision_conflict = (
        isinstance(expected_revision, int)
        and expected_revision != session.question_revision
    )
    return id_conflict or revision_conflict


def _question_conflict_response(input_data: RunAgentInput, session) -> StreamingResponse:
    tools = []
    if session.current_question:
        tools.append(
            _editor_tool(
                session.current_question,
                session,
                replace_code=True,
                initial_code=session.last_code_content,
            )
        )
    return _event_response(
        input_data,
        session,
        text="The active question changed while this request was in progress. I resynced the current task and code.",
        tools=tools,
    )


async def _next_question_from_decision(session, decision: dict, context: str) -> Optional[Question]:
    question = _question_from_data(decision.get("next_question"), session.selected_language)
    if question:
        return question
    return await generate_question_llm(session.session_id, context, session.selected_language)


async def _apply_dynamic_decision(
    session,
    decision: dict,
    trigger: str,
    review: Optional[dict] = None,
) -> tuple[str, list[tuple[str, dict]]]:
    action = str(decision.get("action") or "WAIT_FOR_CANDIDATE").upper()
    message = str(decision.get("message") or "")
    disposition = str(decision.get("question_disposition") or "continue").lower()
    intent = str(decision.get("candidate_intent") or "other").lower()
    current_code = session.last_code_content

    if trigger == "CANDIDATE_MESSAGE" and intent in {"help", "cannot_solve"}:
        session_manager.record_help_request(session.session_id)

    if action == "REPHRASE_QUESTION":
        updated_text = str(decision.get("updated_question_text") or "").strip()
        if updated_text and session.current_question:
            session_manager.rephrase_current_question(session.session_id, updated_text)
            return message, [_editor_tool(session.current_question, session, replace_code=False)]
        return message, []

    wants_replacement = action == "REPLACE_QUESTION"
    wants_next = action == "GENERATE_NEXT_QUESTION"
    replacement_allowed = disposition == "skip" and (
        intent == "skip"
        or (
            intent == "cannot_solve"
            and session.current_question
            and session.current_question.help_request_count >= 2
        )
    )
    next_allowed = disposition == "complete" and (
        trigger == "CODE_REVIEW" or intent == "done"
    )

    if (wants_replacement and replacement_allowed) or (wants_next and next_allowed):
        reason = "skipped" if wants_replacement else "completed"
        next_question = await _next_question_from_decision(
            session,
            decision,
            f"Trigger: {trigger}. Previous outcome: {reason}. Review: {json.dumps(review or {})}",
        )
        if next_question:
            session_manager.complete_question(
                session.session_id,
                review_result=review,
                reason=reason,
                code=current_code,
            )
            session_manager.set_current_question(session.session_id, next_question)
            return message, [_editor_tool(next_question, session, replace_code=True)]
        return "", []

    if wants_replacement or wants_next:
        return "", []

    end_allowed = intent == "end" or (
        trigger == "CODE_REVIEW"
        and disposition == "complete"
        and decision.get("assessment_complete") is True
    )
    if action == "END_INTERVIEW" and end_allowed:
        completion_reason = disposition if disposition in {"complete", "skip"} else "ended"
        session_manager.complete_question(
            session.session_id,
            review_result=review,
            reason=completion_reason,
            code=current_code,
        )
        session_manager.end_interview(session.session_id)
        return message, [("close_editor", {"end_interview": True})]

    if action == "END_INTERVIEW":
        return "", []

    return message, []


async def _handle_snapshot(input_data: RunAgentInput, session, previous_code: str) -> StreamingResponse:
    if _question_conflict(input_data, session):
        return _question_conflict_response(input_data, session)

    now = datetime.now(timezone.utc)
    question = session.current_question
    started = (
        datetime.fromisoformat(question.started_at.replace("Z", "+00:00"))
        if question and question.started_at
        else now
    )
    last_activity = (
        datetime.fromisoformat(session.last_code_activity_at.replace("Z", "+00:00"))
        if session.last_code_activity_at
        else now
    )
    snapshot = CodeSnapshot(
        snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
        question_id=session.current_question_id or "",
        code=session.last_code_content,
        language=session.selected_language,
        timestamp=now.isoformat(),
        question_elapsed_seconds=max(0, int((now - started).total_seconds())),
        inactive_seconds=max(0, int((now - last_activity).total_seconds())),
        code_modified_since_last=session.last_code_content != previous_code,
    )
    session_manager.add_snapshot(session.session_id, snapshot)
    decision = await call_llm_for_decision(
        session.session_id,
        "CODE_SNAPSHOT",
        "Analyze progress silently. Do not rephrase, replace, complete, or generate a question from a snapshot.",
    )
    text = decision.get("message", "") if decision.get("action") == "ASK_CASUAL_QUESTION" else ""
    return _event_response(input_data, session, text=text)


async def _handle_inactivity(input_data: RunAgentInput, session) -> StreamingResponse:
    if _question_conflict(input_data, session):
        return _question_conflict_response(input_data, session)
    decision = await call_llm_for_decision(
        session.session_id,
        "INACTIVITY",
        "The candidate has not edited for at least two minutes. Do not change the active question.",
    )
    allowed_actions = {"ASK_CASUAL_QUESTION", "ASK_FOLLOWUP", "RESPOND_TO_CANDIDATE"}
    text = decision.get("message", "") if decision.get("action") in allowed_actions else ""
    if text:
        session_manager.record_inactivity_prompt(session.session_id)
    return _event_response(input_data, session, text=text)


async def _handle_review(input_data: RunAgentInput, session) -> StreamingResponse:
    if _question_conflict(input_data, session):
        return _question_conflict_response(input_data, session)

    if not session.current_question:
        return _event_response(input_data, session, error="There is no active coding question to review.")

    session.status = InterviewStatus.REVIEWING
    review = await review_code_llm(
        session.session_id,
        session.last_code_content,
        session.selected_language,
    )
    session_manager.record_question_review(session.session_id, review, session.last_code_content)
    decision = await call_llm_for_decision(
        session.session_id,
        "CODE_REVIEW",
        f"The candidate explicitly submitted the latest code for review. Review result: {json.dumps(review)}",
    )
    session.status = InterviewStatus.CODING_ACTIVE
    text, tools = await _apply_dynamic_decision(session, decision, "CODE_REVIEW", review)
    if not text:
        text = str(review.get("feedback") or "")
    if not any(name == "close_editor" for name, _ in tools):
        tools.append(("close_editor", {"end_interview": False}))
    return _event_response(input_data, session, text=text, tools=tools)


async def _handle_coding_chat(input_data: RunAgentInput, session) -> StreamingResponse:
    if _question_conflict(input_data, session):
        return _question_conflict_response(input_data, session)
    if not session.current_question:
        question = await generate_question_llm(session.session_id, language=session.selected_language)
        if not question:
            return _event_response(input_data, session, error="Unable to generate a coding question.")
        session_manager.set_current_question(session.session_id, question)
        return _event_response(input_data, session, tools=[_editor_tool(question, session, replace_code=True)])

    latest_message = _latest_user_message(input_data.messages or [])
    recent_conversation = [
        {
            "role": _message_value(message, "role"),
            "content": (_message_value(message, "content") or "")[:1000],
        }
        for message in (input_data.messages or [])[-8:]
    ]
    decision = await call_llm_for_decision(
        session.session_id,
        "CANDIDATE_MESSAGE",
        "Latest candidate message: "
        + json.dumps(latest_message)
        + "\nRecent conversation: "
        + json.dumps(recent_conversation)
        + "\nRespond naturally. If they are confused, clarify or rephrase without giving the complete solution. "
        + "Only replace after help is requested or the task is explicitly skipped/completed.",
    )
    text, tools = await _apply_dynamic_decision(session, decision, "CANDIDATE_MESSAGE")
    completion_claimed = (
        decision.get("candidate_intent") == "done"
        or _detect_completion_claim(input_data.messages or [])
    )
    if completion_claimed and not any(name == "close_editor" for name, _ in tools):
        tools.append(("close_editor", {"end_interview": False}))
    if not text and not tools:
        text = "I could not determine the next interview step. Please tell me what part you want help with."
    return _event_response(input_data, session, text=text, tools=tools)


def _theoretical_chat_response(input_data: RunAgentInput, session) -> StreamingResponse:
    encoder = EventEncoder()
    prompt = SYSTEM_PROMPT.format(
        questions_asked=session.theoretical_questions_asked,
        confirmation_pending=session.coding_confirmation_pending,
        status=session.status.value,
        language=session.selected_language,
    )
    messages = [{"role": "system", "content": prompt}]
    messages.extend(
        {
            "role": _message_value(message, "role", "user"),
            "content": _message_value(message, "content", "") or "",
        }
        for message in (input_data.messages or [])
    )

    async def stream_events() -> AsyncGenerator[bytes, None]:
        message_id = f"msg_{input_data.run_id}"
        assistant_text = ""
        try:
            yield encoder.encode(
                RunStartedEvent(
                    type=EventType.RUN_STARTED,
                    thread_id=input_data.thread_id,
                    run_id=input_data.run_id,
                    input=input_data,
                )
            )
            payload = {
                **_model_request_fields(),
                "messages": messages,
                "stream": True,
                "temperature": 0.7,
            }
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
                    error_body = (await response.aread()).decode(errors="replace")
                    raise RuntimeError(f"LLM API error {response.status_code}: {error_body}")
                async for line in response.aiter_lines():
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    try:
                        chunk = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    content = choices[0].get("delta", {}).get("content")
                    if not content:
                        continue
                    assistant_text += content
                    yield encoder.encode(
                        TextMessageChunkEvent(
                            type=EventType.TEXT_MESSAGE_CHUNK,
                            message_id=message_id,
                            role="assistant",
                            delta=content,
                        )
                    )

            if "are you comfortable starting the coding round now" in assistant_text.lower():
                session.coding_confirmation_pending = True
            yield encoder.encode(
                StateSnapshotEvent(
                    type=EventType.STATE_SNAPSHOT,
                    snapshot=_state_payload(session),
                )
            )
            yield encoder.encode(
                RunFinishedEvent(
                    type=EventType.RUN_FINISHED,
                    thread_id=input_data.thread_id,
                    run_id=input_data.run_id,
                )
            )
        except Exception as error:
            yield encoder.encode(
                RunErrorEvent(type=EventType.RUN_ERROR, message=str(error), code="LLM_ERROR")
            )
    async def event_generator() -> AsyncGenerator[bytes, None]:
        async with _get_session_lock(session.session_id):
            session.pending_llm_request = True
            try:
                async for event in stream_events():
                    yield event
            finally:
                session.pending_llm_request = False

    return StreamingResponse(event_generator(), media_type=encoder.get_content_type())


def _get_session_lock(session_id: str) -> asyncio.Lock:
    lock = session_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        session_locks[session_id] = lock
    return lock


async def _run_agent_locked(input_data: RunAgentInput, session) -> StreamingResponse:
    if not session_manager.register_run(session.session_id, input_data.run_id):
        return _event_response(input_data, session)

    messages = input_data.messages or []
    session.theoretical_questions_asked = max(
        session.theoretical_questions_asked,
        _count_questions_asked(messages),
    )

    editor_content = _get_editor_content(input_data)
    editor_language = _get_editor_language(input_data)
    request_type = _get_request_type(input_data)
    coding_active = session.status in {
        InterviewStatus.CODING_ACTIVE,
        InterviewStatus.WAITING_FOR_REVIEW,
        InterviewStatus.REVIEWING,
    }

    # Reject stale question state before it can overwrite the active question's code.
    if coding_active and _question_conflict(input_data, session):
        return _question_conflict_response(input_data, session)

    previous_code = session.last_code_content
    session.selected_language = editor_language
    if coding_active:
        session_manager.update_code_activity(
            session.session_id,
            editor_content,
            editor_language,
        )

    if not coding_active and session.coding_confirmation_pending:
        confirmation = _detect_candidate_confirmation(messages)
        if confirmation == "confirmed":
            session.selected_language = editor_language
            question = await generate_question_llm(
                session.session_id,
                "This is the first coding task.",
                editor_language,
            )
            if not question:
                return _event_response(
                    input_data,
                    session,
                    error="Unable to generate the first coding question. Please try again.",
                )
            session_manager.start_coding_session(session.session_id, editor_language)
            session_manager.set_current_question(session.session_id, question)
            return _event_response(
                input_data,
                session,
                tools=[_editor_tool(question, session, replace_code=True)],
            )
        if confirmation is None:
            return _event_response(
                input_data,
                session,
                text="Are you comfortable starting the coding round now?",
            )
        session.coding_confirmation_pending = False

    if not coding_active and _detect_coding_request(messages):
        session.coding_confirmation_pending = True
        return _event_response(
            input_data,
            session,
            text="Are you comfortable starting the coding round now?",
        )

    coding_active = session.status in {
        InterviewStatus.CODING_ACTIVE,
        InterviewStatus.WAITING_FOR_REVIEW,
        InterviewStatus.REVIEWING,
    }
    if coding_active:
        if request_type == "snapshot":
            return await _handle_snapshot(input_data, session, previous_code)
        if request_type == "inactivity":
            return await _handle_inactivity(input_data, session)
        if request_type == "review":
            return await _handle_review(input_data, session)
        return await _handle_coding_chat(input_data, session)

    return _theoretical_chat_response(input_data, session)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "llm_model": OPENAI_MODELS[0],
        "tts_provider": "edge-tts",
        "tts_voice": EDGE_TTS_VOICE,
    }


@app.post("/tts")
async def synthesize_speech(tts_request: TTSRequest):
    text = re.sub(r"\s+", " ", tts_request.text).strip()
    if not text:
        raise HTTPException(status_code=422, detail="Speech text cannot be empty.")

    voice = tts_request.voice or EDGE_TTS_VOICE
    if voice not in EDGE_TTS_VOICES:
        raise HTTPException(status_code=400, detail="Unsupported Edge TTS voice.")

    communicate = edge_tts.Communicate(
        text,
        voice,
        rate=EDGE_TTS_RATE,
        volume=EDGE_TTS_VOLUME,
    )

    async def audio_stream() -> AsyncGenerator[bytes, None]:
        async with tts_semaphore:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio" and chunk.get("data"):
                    yield chunk["data"]

    return StreamingResponse(
        audio_stream(),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-TTS-Voice": voice,
        },
    )


@app.post("/tts/segment")
async def synthesize_speech_segment(tts_request: TTSRequest):
    text = re.sub(r"\s+", " ", tts_request.text).strip()
    if not text:
        raise HTTPException(status_code=422, detail="Speech text cannot be empty.")

    voice = tts_request.voice or EDGE_TTS_VOICE
    if voice not in EDGE_TTS_VOICES:
        raise HTTPException(status_code=400, detail="Unsupported Edge TTS voice.")

    communicate = edge_tts.Communicate(
        text,
        voice,
        rate=EDGE_TTS_RATE,
        volume=EDGE_TTS_VOLUME,
        boundary="WordBoundary",
    )
    audio = bytearray()
    boundaries = []

    try:
        async with tts_semaphore:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio" and chunk.get("data"):
                    audio.extend(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    boundaries.append(
                        {
                            "text": chunk.get("text", ""),
                            "offsetMs": round(float(chunk.get("offset", 0)) / 10_000, 2),
                            "durationMs": round(float(chunk.get("duration", 0)) / 10_000, 2),
                        }
                    )
    except Exception as error:
        print(f"Edge TTS synthesis failed: {error}")
        raise HTTPException(status_code=502, detail="Speech synthesis is temporarily unavailable.") from error

    if not audio:
        raise HTTPException(status_code=502, detail="Speech synthesis returned no audio.")

    duration_ms = max(
        (boundary["offsetMs"] + boundary["durationMs"] for boundary in boundaries),
        default=0,
    )
    return {
        "audio": base64.b64encode(audio).decode("ascii"),
        "mimeType": "audio/mpeg",
        "boundaries": boundaries,
        "durationMs": round(duration_ms, 2),
        "voice": voice,
    }


@app.post("/")
async def run_agent(request: Request):
    body = await request.json()
    if isinstance(body.get("messages"), list):
        for message in body["messages"]:
            if isinstance(message, dict) and not message.get("id"):
                message["id"] = f"msg_{uuid.uuid4().hex[:8]}"

    input_data = RunAgentInput(**body)
    session_id = _get_session_id(input_data)
    session = session_manager.get_session(session_id) if session_id else None
    if not session:
        session = session_manager.get_session_by_thread(input_data.thread_id)
    if not session:
        session = session_manager.create_session(input_data.thread_id)

    async with _get_session_lock(session.session_id):
        return await _run_agent_locked(input_data, session)


@app.on_event("shutdown")
async def shutdown_event():
    await http_client.aclose()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
