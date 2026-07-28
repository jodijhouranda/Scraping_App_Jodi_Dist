import re

def parse_kamus():
    try:
        with open('d:/Kantor/Code/SEJodi/monitoringKualitas/Kamus_Variabel_Final.md', 'r', encoding='utf-8') as f:
            content = f.read()
            
        blocks = {}
        current_block = "General"
        
        for line in content.split('\n'):
            if line.startswith('## 📁'):
                current_block = line.replace('## 📁', '').strip()
                blocks[current_block] = []
            elif line.startswith('|') and not line.startswith('| No |') and not line.startswith('|:--:'):
                parts = [p.strip() for p in line.split('|')]
                if len(parts) > 4:
                    var_name = parts[2].replace('`', '').strip()
                    question = parts[4].strip()
                    if var_name:
                        blocks[current_block].append({'var': var_name, 'question': question})
        
        for k, v in blocks.items():
            print(f"Block: {k} - {len(v)} variables")
            if v:
                print(f"  First var: {v[0]}")
    except Exception as e:
        print(f"Error: {e}")

parse_kamus()
