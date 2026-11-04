import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class InterviewAction(str, Enum):
    GENERATE_FIRST_QUESTION = "GENERATE_FIRST_QUESTION"
    ANALYZE_CODE = "ANALYZE_CODE"
    ASK_CASUAL_QUESTION = "ASK_CASUAL_QUESTION"
    REVIEW_CODE = "REVIEW_CODE"
    ASK_FOLLOWUP = "ASK_FOLLOWUP"
    REPHRASE_QUESTION = "REPHRASE_QUESTION"
    REPLACE_QUESTION = "REPLACE_QUESTION"
    RESPOND_TO_CANDIDATE = "RESPOND_TO_CANDIDATE"
    GENERATE_NEXT_QUESTION = "GENERATE_NEXT_QUESTION"
    WAIT_FOR_CANDIDATE = "WAIT_FOR_CANDIDATE"
    END_INTERVIEW = "END_INTERVIEW"


class InterviewStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    CODING_ACTIVE = "CODING_ACTIVE"
    WAITING_FOR_REVIEW = "WAITING_FOR_REVIEW"
    REVIEWING = "REVIEWING"
    ENDED = "ENDED"


@dataclass
class Question:
    question_id: str
    question_text: str
    concept: str
    difficulty: str
    estimated_minutes: int
    generated_at: str
    starter_code: str = ""
    language: str = "python"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    completion_reason: Optional[str] = None
    candidate_code: str = ""
    review_result: Optional[dict] = None
    rephrases: list = field(default_factory=list)
    help_request_count: int = 0


@dataclass
class CodeSnapshot:
    snapshot_id: str
    question_id: str
    code: str
    language: str
    timestamp: str
    question_elapsed_seconds: int
    inactive_seconds: int
    code_modified_since_last: bool


@dataclass
class InterviewSession:
    session_id: str
    thread_id: str
    status: InterviewStatus = InterviewStatus.NOT_STARTED
    
    interview_started_at: Optional[str] = None
    editor_opened_at: Optional[str] = None
    first_question_generated_at: Optional[str] = None
    interview_ended_at: Optional[str] = None
    
    current_question_id: Optional[str] = None
    current_question: Optional[Question] = None
    question_history: list = field(default_factory=list)
    question_revision: int = 0

    selected_language: str = "python"
    theoretical_questions_asked: int = 0
    coding_confirmation_pending: bool = False
    
    code_snapshots: list = field(default_factory=list)
    last_code_activity_at: Optional[str] = None
    last_code_content: str = ""
    last_snapshot_sent_at: Optional[str] = None
    
    last_inactivity_prompt_at: Optional[str] = None
    inactivity_prompt_count: int = 0
    
    total_questions_attempted: int = 0
    concepts_tested: list = field(default_factory=list)
    candidate_strengths: list = field(default_factory=list)
    candidate_weaknesses: list = field(default_factory=list)
    
    pending_llm_request: bool = False
    last_llm_request_id: Optional[str] = None
    processed_run_ids: list = field(default_factory=list)


class InterviewSessionManager:
    def __init__(self):
        self.sessions: dict[str, InterviewSession] = {}
    
    def create_session(self, thread_id: str) -> InterviewSession:
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        
        session = InterviewSession(
            session_id=session_id,
            thread_id=thread_id,
            interview_started_at=now,
        )
        self.sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[InterviewSession]:
        return self.sessions.get(session_id)
    
    def get_session_by_thread(self, thread_id: str) -> Optional[InterviewSession]:
        for session in self.sessions.values():
            if session.thread_id == thread_id:
                return session
        return None
    
    def update_session(self, session_id: str, **kwargs) -> Optional[InterviewSession]:
        session = self.sessions.get(session_id)
        if session:
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)
        return session
    
    def start_coding_session(self, session_id: str, language: str = "python", code: str = "") -> InterviewSession:
        session = self.sessions.get(session_id)
        if session:
            now = datetime.now(timezone.utc).isoformat()
            session.editor_opened_at = now
            session.status = InterviewStatus.CODING_ACTIVE
            session.last_code_activity_at = now
            session.last_code_content = code
            session.selected_language = language or "python"
            session.coding_confirmation_pending = False
        return session
    
    def set_current_question(self, session_id: str, question: Question) -> InterviewSession:
        session = self.sessions.get(session_id)
        if session:
            if session.current_question and not session.current_question.completed_at:
                raise ValueError("Complete or skip the active question before replacing it")
            session.current_question_id = question.question_id
            session.current_question = question
            session.question_history.append(question)
            session.question_revision += 1
            session.total_questions_attempted += 1
            if question.concept not in session.concepts_tested:
                session.concepts_tested.append(question.concept)
            now = datetime.now(timezone.utc).isoformat()
            if session.first_question_generated_at is None:
                session.first_question_generated_at = now
            question.started_at = now
            session.last_code_activity_at = now
            session.last_code_content = question.starter_code
            session.selected_language = question.language or session.selected_language
            session.last_snapshot_sent_at = None
            session.inactivity_prompt_count = 0
            session.last_inactivity_prompt_at = None
        return session
    
    def update_code_activity(self, session_id: str, code: str, language: Optional[str] = None) -> InterviewSession:
        session = self.sessions.get(session_id)
        if session:
            now = datetime.now(timezone.utc).isoformat()
            code_modified = code != session.last_code_content
            if code_modified or session.last_code_activity_at is None:
                session.last_code_activity_at = now
            session.last_code_content = code
            if language:
                session.selected_language = language
            if session.current_question and session.current_question.started_at:
                session.current_question.candidate_code = code
        return session

    def register_run(self, session_id: str, run_id: str) -> bool:
        """Return False for a duplicate request and remember recent run IDs."""
        session = self.sessions.get(session_id)
        if not session:
            return False
        if run_id in session.processed_run_ids:
            return False
        session.processed_run_ids.append(run_id)
        del session.processed_run_ids[:-100]
        return True
    
    def add_snapshot(self, session_id: str, snapshot: CodeSnapshot) -> InterviewSession:
        session = self.sessions.get(session_id)
        if session:
            session.code_snapshots.append(snapshot)
            session.last_snapshot_sent_at = snapshot.timestamp
        return session
    
    def record_inactivity_prompt(self, session_id: str) -> InterviewSession:
        session = self.sessions.get(session_id)
        if session:
            now = datetime.now(timezone.utc).isoformat()
            session.last_inactivity_prompt_at = now
            session.inactivity_prompt_count += 1
        return session
    
    def record_question_review(self, session_id: str, review_result: dict, code: str) -> InterviewSession:
        session = self.sessions.get(session_id)
        if session and session.current_question:
            session.current_question.review_result = review_result
            session.current_question.candidate_code = code
        return session

    def rephrase_current_question(self, session_id: str, question_text: str) -> InterviewSession:
        session = self.sessions.get(session_id)
        if session and session.current_question and question_text.strip():
            session.current_question.rephrases.append({
                "question_text": session.current_question.question_text,
                "rephrased_at": datetime.now(timezone.utc).isoformat(),
            })
            session.current_question.question_text = question_text.strip()
            session.question_revision += 1
        return session

    def record_help_request(self, session_id: str) -> InterviewSession:
        session = self.sessions.get(session_id)
        if session and session.current_question:
            session.current_question.help_request_count += 1
        return session

    def complete_question(
        self,
        session_id: str,
        review_result: Optional[dict] = None,
        reason: str = "completed",
        code: Optional[str] = None,
    ) -> InterviewSession:
        session = self.sessions.get(session_id)
        if session and session.current_question:
            now = datetime.now(timezone.utc).isoformat()
            session.current_question.completed_at = now
            session.current_question.completion_reason = reason
            if review_result is not None:
                session.current_question.review_result = review_result
            if code is not None:
                session.current_question.candidate_code = code
            session.status = InterviewStatus.CODING_ACTIVE
        return session
    
    def end_interview(self, session_id: str) -> InterviewSession:
        session = self.sessions.get(session_id)
        if session:
            now = datetime.now(timezone.utc).isoformat()
            session.interview_ended_at = now
            session.status = InterviewStatus.ENDED
        return session
    
    def to_dict(self, session: InterviewSession) -> dict:
        return {
            "session_id": session.session_id,
            "thread_id": session.thread_id,
            "status": session.status.value,
            "interview_started_at": session.interview_started_at,
            "editor_opened_at": session.editor_opened_at,
            "first_question_generated_at": session.first_question_generated_at,
            "interview_ended_at": session.interview_ended_at,
            "current_question_id": session.current_question_id,
            "current_question": asdict(session.current_question) if session.current_question else None,
            "question_history": [asdict(q) for q in session.question_history],
            "question_revision": session.question_revision,
            "selected_language": session.selected_language,
            "editor_code": session.last_code_content,
            "coding_round_active": session.status in {
                InterviewStatus.CODING_ACTIVE,
                InterviewStatus.WAITING_FOR_REVIEW,
                InterviewStatus.REVIEWING,
            },
            "coding_confirmation_pending": session.coding_confirmation_pending,
            "questions_asked": session.theoretical_questions_asked,
            "code_snapshots_count": len(session.code_snapshots),
            "last_code_activity_at": session.last_code_activity_at,
            "last_inactivity_prompt_at": session.last_inactivity_prompt_at,
            "inactivity_prompt_count": session.inactivity_prompt_count,
            "total_questions_attempted": session.total_questions_attempted,
            "concepts_tested": session.concepts_tested,
            "candidate_strengths": session.candidate_strengths,
            "candidate_weaknesses": session.candidate_weaknesses,
        }


session_manager = InterviewSessionManager()


def create_llm_decision_prompt(session: InterviewSession, trigger: str, extra_context: str = "") -> str:
    current_q = session.current_question
    history_summary = ""
    for q in session.question_history[-3:]:
        history_summary += f"- {q.question_text[:100]} (concept: {q.concept}, difficulty: {q.difficulty})\n"
    
    snapshot_info = ""
    if session.code_snapshots:
        last_snap = session.code_snapshots[-1]
        snapshot_info = f"Latest code snapshot: {last_snap.code[:500]}... (at {last_snap.timestamp}, inactive for {last_snap.inactive_seconds}s)"
    
    return f"""You are the decision engine for an adaptive live coding interview.

CURRENT SESSION STATE:
- Session ID: {session.session_id}
- Interview Status: {session.status.value}
- Editor Opened: {session.editor_opened_at}
- Current Question: {current_q.question_text if current_q else "None"}
- Current Question Concept: {current_q.concept if current_q else "None"}
- Current Question Difficulty: {current_q.difficulty if current_q else "None"}
- Question Started: {current_q.started_at if current_q else "None"}
- Time on Current Question: {(datetime.now(timezone.utc) - datetime.fromisoformat(current_q.started_at.replace('Z', '+00:00'))).total_seconds() if current_q and current_q.started_at else 0:.0f} seconds
- Selected Language: {session.selected_language}
- Candidate's Current Code (latest authoritative editor state):
{session.last_code_content[:4000] if session.last_code_content else "(empty)"}
- Last Code Activity: {session.last_code_activity_at}
- Seconds Since Last Keystroke: {(datetime.now(timezone.utc) - datetime.fromisoformat(session.last_code_activity_at.replace('Z', '+00:00'))).total_seconds() if session.last_code_activity_at else 0:.0f}
- Inactivity Prompts Sent: {session.inactivity_prompt_count}
- Last Inactivity Prompt: {session.last_inactivity_prompt_at}
- Total Questions Attempted: {session.total_questions_attempted}
- Concepts Tested: {session.concepts_tested}
- Candidate Strengths: {session.candidate_strengths}
- Candidate Weaknesses: {session.candidate_weaknesses}

RECENT QUESTION HISTORY:
{history_summary if history_summary else "No previous questions"}

{snapshot_info}

TRIGGER: {trigger}
{extra_context}

DECISION REQUIRED:
Based on the above context, decide the next action. Return ONLY a JSON object with this exact structure:

{{
  "action": "ANALYZE_CODE|ASK_CASUAL_QUESTION|ASK_FOLLOWUP|REPHRASE_QUESTION|REPLACE_QUESTION|RESPOND_TO_CANDIDATE|GENERATE_NEXT_QUESTION|WAIT_FOR_CANDIDATE|END_INTERVIEW",
  "reason": "Brief explanation of why this action was chosen",
  "message": "Natural interviewer message to show candidate (or empty string if no message)",
  "candidate_intent": "coding|help|cannot_solve|done|skip|end|other",
  "question_disposition": "continue|complete|skip",
  "assessment_complete": false,
  "updated_question_text": "A clearer wording of the SAME task when action is REPHRASE_QUESTION, otherwise null",
  "next_question": {{
    "question_text": "Full question description with requirements",
    "concept": "Programming concept being tested",
    "difficulty": "easy|medium|hard",
    "estimated_minutes": 3,
    "starter_code": "Optional starter code template"
  }} | null,
  "evaluation": {{
    "correctness": "acceptable|partial|incorrect",
    "concept_understanding": "good|developing|insufficient",
    "issues": ["list of specific issues found"],
    "feedback": "Constructive feedback for candidate"
  }} | null
}}

RULES:
1. Every decision must use the latest code and selected language above.
2. ANALYZE_CODE is for snapshots. Never change a question from a snapshot.
3. ASK_CASUAL_QUESTION is only an encouraging inactivity check-in.
4. ASK_FOLLOWUP or RESPOND_TO_CANDIDATE can provide a small hint, clarification, or ask about the approach. Never reveal a complete solution.
5. REPHRASE_QUESTION keeps the same task and existing code. Use it when clearer wording would help.
6. REPLACE_QUESTION is allowed only when the candidate asks to skip/change the task or remains unable to proceed after help. Set question_disposition="skip" and provide next_question.
7. GENERATE_NEXT_QUESTION is for a completed task. Set question_disposition="complete" and adapt difficulty from the review and history.
8. WAIT_FOR_CANDIDATE is the default while the candidate is actively coding. Never replace an active question merely because a snapshot is incomplete.
9. END_INTERVIEW only when the candidate explicitly asks to end, or immediately after a completed review when the available evidence is sufficient. Set assessment_complete=true in the latter case.

For questions: Target 3-4 minute tasks. Test fundamentals first, adapt difficulty.
For inactivity messages: Natural, conversational, NOT robotic. Examples: "How are you thinking about approaching this one?" "Any part you're finding tricky?"
For reviews: Be thorough but encouraging. Never give away solutions.
"""


def parse_llm_decision(response_text: str) -> dict:
    try:
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = response_text[start:end]
            return json.loads(json_str)
    except Exception:
        pass
    return {
        "action": "WAIT_FOR_CANDIDATE",
        "reason": "Failed to parse LLM decision",
        "message": "",
        "candidate_intent": "other",
        "question_disposition": "continue",
        "assessment_complete": False,
        "updated_question_text": None,
        "next_question": None,
        "evaluation": None
    }
