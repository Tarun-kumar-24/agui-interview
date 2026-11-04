import json
import unittest

from fastapi import Request

import main
from interview_session import InterviewStatus, Question, session_manager


def make_request(payload: dict) -> Request:
    body = json.dumps(payload).encode()
    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
            "client": ("test", 50000),
            "server": ("test", 80),
        },
        receive,
    )


async def response_events(response) -> list[dict]:
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.encode() if isinstance(chunk, str) else chunk)
    payload = b"".join(chunks).decode()
    events = []
    for block in payload.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
                break
    return events


def input_payload(
    thread_id: str,
    run_id: str,
    messages: list[dict],
    *,
    session_id: str | None = None,
    request_type: str = "chat",
    code: str = "",
    question_id: str | None = None,
    question_revision: int = 0,
) -> dict:
    return {
        "threadId": thread_id,
        "runId": run_id,
        "state": {
            "requestType": request_type,
            "editorContent": code,
            "editorOpen": session_id is not None,
            "editorLanguage": "python",
            "sessionId": session_id,
            "questionId": question_id,
            "questionRevision": question_revision,
        },
        "messages": messages,
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }


def question(text: str = "Return the sum of two integers.") -> Question:
    return Question(
        question_id="q_initial",
        question_text=text,
        concept="functions",
        difficulty="easy",
        estimated_minutes=3,
        generated_at="2026-01-01T00:00:00+00:00",
        starter_code="def add(a, b):\n    pass",
        language="python",
    )


class InterviewWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        session_manager.sessions.clear()

    async def test_confirmation_emits_real_question_without_placeholder(self):
        thread_id = "thread_confirmation"
        first_messages = [
            {"id": "u1", "role": "user", "content": "Can we start the coding round?"},
        ]
        first_response = await main.run_agent(
            make_request(input_payload(thread_id, "run_1", first_messages))
        )
        first_events = await response_events(first_response)
        finished = next(event for event in first_events if event["type"] == "RUN_FINISHED")
        session_id = finished["state"]["sessionId"]

        original_generate = main.generate_question_llm

        async def fake_generate(*_args, **_kwargs):
            return question()

        main.generate_question_llm = fake_generate
        try:
            second_messages = [
                *first_messages,
                {
                    "id": "a1",
                    "role": "assistant",
                    "content": "Are you comfortable starting the coding round now?",
                },
                {"id": "u2", "role": "user", "content": "Yes, I am ready."},
            ]
            second_response = await main.run_agent(
                make_request(
                    input_payload(
                        thread_id,
                        "run_2",
                        second_messages,
                        session_id=session_id,
                    )
                )
            )
            second_events = await response_events(second_response)
        finally:
            main.generate_question_llm = original_generate

        tool_event = next(event for event in second_events if event["type"] == "TOOL_CALL_CHUNK")
        tool_args = json.loads(tool_event["delta"])
        session = session_manager.get_session(session_id)

        self.assertEqual(tool_event["toolCallName"], "open_editor")
        self.assertEqual(tool_args["task"], "Return the sum of two integers.")
        self.assertNotEqual(tool_args["task"], "Starting coding round...")
        self.assertTrue(tool_args["replace_code"])
        self.assertEqual(session.status, InterviewStatus.CODING_ACTIVE)
        self.assertEqual(session.current_question_id, "q_initial")

    async def test_review_uses_latest_request_code(self):
        session = session_manager.create_session("thread_review")
        session_manager.start_coding_session(session.session_id, "python")
        session_manager.set_current_question(session.session_id, question())
        captured = {}

        original_review = main.review_code_llm
        original_decision = main.call_llm_for_decision

        async def fake_review(session_id, code, language):
            captured.update(session_id=session_id, code=code, language=language)
            return {
                "correctness": "partial",
                "concept_understanding": "developing",
                "issues": ["Missing return"],
                "feedback": "Your structure is sound; check what the function returns.",
            }

        async def fake_decision(*_args, **_kwargs):
            return {
                "action": "ASK_FOLLOWUP",
                "message": "What value should this function return?",
                "candidate_intent": "done",
                "question_disposition": "continue",
                "next_question": None,
            }

        main.review_code_llm = fake_review
        main.call_llm_for_decision = fake_decision
        latest_code = "def add(a, b):\n    return a + b"
        try:
            response = await main.run_agent(
                make_request(
                    input_payload(
                        session.thread_id,
                        "run_review",
                        [{"id": "u1", "role": "user", "content": "Please review it."}],
                        session_id=session.session_id,
                        request_type="review",
                        code=latest_code,
                        question_id=session.current_question_id,
                        question_revision=session.question_revision,
                    )
                )
            )
            events = await response_events(response)
        finally:
            main.review_code_llm = original_review
            main.call_llm_for_decision = original_decision

        text = "".join(
            event.get("delta", "")
            for event in events
            if event["type"] == "TEXT_MESSAGE_CHUNK"
        )
        self.assertEqual(captured["code"], latest_code)
        self.assertEqual(session.last_code_content, latest_code)
        self.assertEqual(session.current_question.candidate_code, latest_code)
        self.assertIn("What value", text)
        close_event = next(
            event
            for event in events
            if event["type"] == "TOOL_CALL_CHUNK" and event["toolCallName"] == "close_editor"
        )
        self.assertFalse(json.loads(close_event["delta"])["end_interview"])

    async def test_completion_message_hides_editor_without_ending_session(self):
        session = session_manager.create_session("thread_complete_message")
        session_manager.start_coding_session(session.session_id, "python")
        session_manager.set_current_question(session.session_id, question())

        original_decision = main.call_llm_for_decision

        async def fake_decision(*_args, **_kwargs):
            return {
                "action": "RESPOND_TO_CANDIDATE",
                "message": "I will review the solution you completed.",
                "candidate_intent": "other",
                "question_disposition": "continue",
            }

        main.call_llm_for_decision = fake_decision
        try:
            response = await main.run_agent(
                make_request(
                    input_payload(
                        session.thread_id,
                        "run_complete_message",
                        [{"id": "u1", "role": "user", "content": "I have complete this"}],
                        session_id=session.session_id,
                        request_type="chat",
                        code="def add(a, b):\n    return a + b",
                        question_id=session.current_question_id,
                        question_revision=session.question_revision,
                    )
                )
            )
            events = await response_events(response)
        finally:
            main.call_llm_for_decision = original_decision

        close_event = next(
            event
            for event in events
            if event["type"] == "TOOL_CALL_CHUNK" and event["toolCallName"] == "close_editor"
        )
        self.assertFalse(json.loads(close_event["delta"])["end_interview"])
        self.assertEqual(session.status, InterviewStatus.CODING_ACTIVE)

    async def test_stale_revision_cannot_overwrite_current_question_code(self):
        session = session_manager.create_session("thread_stale")
        session_manager.start_coding_session(session.session_id, "python")
        session_manager.set_current_question(session.session_id, question())
        server_code = "def add(a, b):\n    return a + b"
        session_manager.update_code_activity(session.session_id, server_code, "python")

        response = await main.run_agent(
            make_request(
                input_payload(
                    session.thread_id,
                    "run_stale",
                    [],
                    session_id=session.session_id,
                    request_type="snapshot",
                    code="stale code from an earlier revision",
                    question_id=session.current_question_id,
                    question_revision=session.question_revision - 1,
                )
            )
        )
        events = await response_events(response)
        tool_event = next(event for event in events if event["type"] == "TOOL_CALL_CHUNK")
        tool_args = json.loads(tool_event["delta"])

        self.assertEqual(session.last_code_content, server_code)
        self.assertEqual(session.current_question.candidate_code, server_code)
        self.assertEqual(tool_args["initial_code"], server_code)
        self.assertTrue(tool_args["replace_code"])

    async def test_rephrase_preserves_code_and_replacement_preserves_history(self):
        session = session_manager.create_session("thread_transitions")
        session_manager.start_coding_session(session.session_id, "python")
        session_manager.set_current_question(session.session_id, question())
        latest_code = "def add(a, b):\n    return a + b"
        session_manager.update_code_activity(session.session_id, latest_code, "python")

        rephrase = {
            "action": "REPHRASE_QUESTION",
            "message": "Here is the same task in simpler wording.",
            "candidate_intent": "help",
            "question_disposition": "continue",
            "updated_question_text": "Write a function that adds two integer inputs and returns the result.",
        }
        _, rephrase_tools = await main._apply_dynamic_decision(
            session, rephrase, "CANDIDATE_MESSAGE"
        )

        self.assertEqual(session.last_code_content, latest_code)
        self.assertEqual(len(session.question_history), 1)
        self.assertFalse(rephrase_tools[0][1]["replace_code"])
        self.assertEqual(len(session.current_question.rephrases), 1)

        unsafe_replacement = {
            "action": "REPLACE_QUESTION",
            "message": "",
            "candidate_intent": "coding",
            "question_disposition": "continue",
            "next_question": {
                "question_text": "Unsafe replacement",
                "concept": "loops",
                "difficulty": "medium",
                "starter_code": "",
            },
        }
        _, unsafe_tools = await main._apply_dynamic_decision(
            session, unsafe_replacement, "CANDIDATE_MESSAGE"
        )
        self.assertEqual(unsafe_tools, [])
        self.assertEqual(len(session.question_history), 1)

        safe_replacement = {
            **unsafe_replacement,
            "candidate_intent": "cannot_solve",
            "question_disposition": "skip",
            "next_question": {
                "question_text": "Return the largest value in a list.",
                "concept": "loops",
                "difficulty": "easy",
                "starter_code": "def largest(values):\n    pass",
            },
        }
        _, replacement_tools = await main._apply_dynamic_decision(
            session, safe_replacement, "CANDIDATE_MESSAGE"
        )

        self.assertEqual(len(session.question_history), 2)
        self.assertEqual(session.question_history[0].completion_reason, "skipped")
        self.assertEqual(session.question_history[0].candidate_code, latest_code)
        self.assertEqual(session.current_question.question_text, "Return the largest value in a list.")
        self.assertTrue(replacement_tools[0][1]["replace_code"])


if __name__ == "__main__":
    unittest.main()
