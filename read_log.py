import json, glob, os
with open('E:/Dev_Workspace/01_Projects/Special/med-agent/read_log.txt', 'w', encoding='utf-8') as out:
    files = sorted(glob.glob('E:/Dev_Workspace/01_Projects/Special/med-agent/LLM_output/*.json'), key=os.path.getmtime)
    for f in files[-5:]:
        data = json.load(open(f, encoding='utf-8'))
        msgs = data.get('outputs', {}).get('messages', [])
        if not msgs:
            msgs = data.get('inputs', {}).get('messages', [])
        out.write(f"\n--- {os.path.basename(f)} ({len(msgs)} msgs) ---\n")
        for m in msgs[-4:]:
            role = m.get('type', m.get('role', 'unknown'))
            name = m.get('name', '')
            content = m.get('content', '')
            if isinstance(content, list): content = str(content)
            out.write(f"[{role}] {name}: {content[:300].replace(chr(10), ' ')}\n")
            if m.get('tool_calls'):
                out.write(f"  Tools: {[t.get('name') for t in m.get('tool_calls')]}\n")
