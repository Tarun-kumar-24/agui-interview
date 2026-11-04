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
    prompt = "Generate a SMALL, focused coding task (3-4 minutes) that tests a fundamental programming concept. Return ONLY a JSON object with keys: question_text, concept, difficulty, estimated_minutes, starter_code"
    
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
        async with client.stream('POST', OPENAI_BASE_URL + '/chat/completions', json=payload, headers=headers) as response:
            print('Status:', response.status_code)
            full_response = ''
            async for line in response.aiter_lines():
                if not line or not line.startswith('data: '):
                    continue
                if line == 'data: [DONE]':
                    break
                try:
                    chunk_data = json.loads(line[6:])
                    choices = chunk_data.get('choices', [])
                    if choices:
                        delta = choices[0].get('delta', {})
                        content = delta.get('content')
                        if content:
                            full_response += content
                except Exception as e:
                    print('Error:', e)
            print('Full response:', full_response)

asyncio.run(test())