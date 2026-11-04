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
    prompt = "Return a JSON object with keys: name, age. Example: {\"name\": \"John\", \"age\": 30}"
    
    payload = {
        'model': OPENAI_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'stream': False,
        'temperature': 0.3,
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