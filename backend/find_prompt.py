with open(r'C:\Users\TARUN KANTIWAL\Documents\agui\agui-interview\backend\main.py', 'r') as f:
    content = f.read()

idx = content.find('SYSTEM_PROMPT =')
if idx >= 0:
    first = content.find('"""', idx)
    second = content.find('"""', first + 3)
    if second >= 0:
        print(content[idx:second+3])