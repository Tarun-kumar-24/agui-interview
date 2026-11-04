import sys
sys.path.insert(0, '.')
import asyncio
import httpx
import json
import os
from dotenv import load_dotenv
load_dotenv('.env')

OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL')

async def test():
    prompt = """You are an adaptive technical interviewer generating the next coding question.

SESSION CONTEXT:
- Questions so far: 0
- Concepts tested: none yet
- Candidate strengths: unknown
- Candidate weaknesses: unknown
- Last question: none

Generate a SMALL, focused coding task (3-4 minutes) that:
1. Tests a fundamental programming concept
2. Adapts difficulty based on performance
3. Builds on previous questions when appropriate
4. Is NOT a repeat of already tested concepts

Return ONLY a JSON object:
{
  "question_text": "Full task description with requirements, input/output examples, and expected scope",
  "concept": "Programming concept being tested (e.g., constructors, loops, functions, arrays, conditionals, classes)",
  "difficulty": "easy|medium|hard",
  "estimated_minutes": 3,
  "starter_code": "Optional starter template (class/function signature only)"
}"""
    
    payload = {
        'model': OPENAI_MODEL,
        'messages': [{'role': 'system', 'content': prompt}],
        'stream': False,
        'temperature': 0.4,
        'response_format': {'type': 'json_object'},
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + OPENAI_API_KEY,
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(OPENAI_BASE_URL + '/chat/completions', json=payload, headers=headers)
        print('Status:', response.status_code)
        print('Response:', response.text)

asyncio.run(test())