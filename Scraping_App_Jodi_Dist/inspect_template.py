import json, re

with open('template.json', encoding='utf-8') as f:
    template = json.load(f)

# Top-level structure
comps = template['components'][0]  # list of panels
print(f"Total top-level panels: {len(comps)}")
for i, c in enumerate(comps):
    label = c.get('label', '???')
    ctype = c.get('type', '???')
    num_children = len(c.get('components', []))
    print(f"  [{i}] type={ctype} label='{label}' children={num_children}")
    
    # Show first level children
    for j, child in enumerate(c.get('components', [])[:5]):
        clabel = child.get('label', '')
        ckey = child.get('dataKey', child.get('key', ''))
        ctype2 = child.get('type', '')
        # Clean HTML
        clabel_clean = re.sub(r'<style.*?</style>', '', clabel, flags=re.DOTALL) if isinstance(clabel, str) else ''
        clabel_clean = re.sub(r'<[^>]+>', '', clabel_clean).strip()
        clabel_clean = clabel_clean[:80]
        print(f"    [{j}] type={ctype2} key='{ckey}' label='{clabel_clean}'")
    if len(c.get('components', [])) > 5:
        print(f"    ... and {len(c.get('components', [])) - 5} more")
