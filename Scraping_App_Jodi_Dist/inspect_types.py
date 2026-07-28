import json

d = json.load(open('template.json', encoding='utf-8'))

# Walk down to find actual input component structure
def find_first_input(node, depth=0):
    if isinstance(node, list):
        for item in node:
            r = find_first_input(item, depth)
            if r:
                return r
    elif isinstance(node, dict):
        ntype = node.get('type')
        key = node.get('dataKey', '')
        if isinstance(ntype, int) and ntype not in [1] and key:
            return node
        for k in ['components', 'columns', 'rows']:
            if k in node:
                r = find_first_input(node[k], depth+1)
                if r:
                    return r
    return None

# Find a few different type examples
types_seen = {}
def collect_types(node):
    if isinstance(node, list):
        for item in node:
            collect_types(item)
    elif isinstance(node, dict):
        ntype = node.get('type')
        key = node.get('dataKey', '')
        if isinstance(ntype, int) and ntype not in [1] and key and ntype not in types_seen:
            types_seen[ntype] = {
                'dataKey': key,
                'label': node.get('label', '')[:50],
                'type': ntype,
                'inputType': node.get('inputType', ''),
                'widget': node.get('widget', ''),
                'values': str(node.get('values', ''))[:100] if node.get('values') else '',
            }
        for k in ['components', 'columns', 'rows']:
            if k in node:
                collect_types(node[k])

collect_types(d['components'])
for t, info in sorted(types_seen.items()):
    print(f"type={t}: inputType={info['inputType']}, widget={info['widget']}, key={info['dataKey']}, label={info['label'][:40]}")
