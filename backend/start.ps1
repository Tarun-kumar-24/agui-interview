cd 'C:\Users\TARUN KANTIWAL\Documents\agui\agui-interview\backend'
$env:OPENAI_API_KEY="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"
$env:OPENAI_BASE_URL="https://integrate.api.nvidia.com/v1"
$env:OPENAI_MODEL="poolside/laguna-xs-2.1"
python -m uvicorn main:app --host 0.0.0.0 --port 8000