import json

with open('klik_api_log.json', encoding='utf-8') as f:
    d = json.load(f)

keys = [k for k in d.keys() if 'get-by-assignment-id' in k]
if not keys:
    print("No get-by-assignment-id found")
    exit()

data_str = d[keys[0]]['data']['data']
parsed = json.loads(data_str)
answers = parsed.get('answers', [])

print(f"Total answers: {len(answers)}")

arrays = []
for x in answers:
    ans = x.get('answer')
    if isinstance(ans, str) and '[{"' in ans.replace(" ", ""):
        arrays.append(x)

if arrays:
    print("Found array answers:")
    for a in arrays:
        print(a['dataKey'])
        print(a['answer'][:200] + '...')
else:
    print("No array answers found")
