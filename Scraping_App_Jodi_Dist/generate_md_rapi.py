import json
import re

def extract_markdown(components, file, level=2):
    for comp in components:
        if isinstance(comp, list):
            extract_markdown(comp, file, level)
            continue
            
        key = comp.get('dataKey', '') or comp.get('key', '')
        label = comp.get('label', '')
        comp_type = comp.get('type', '')
        
        label_no_style = re.sub(r'<style.*?</style>', '', label, flags=re.DOTALL) if isinstance(label, str) else ''
        clean_label = re.sub(r'<[^<]+>', '', label_no_style).strip()
        
        if comp_type == 1 or comp_type in ['panel', 'fieldset', 'tab']:
            # This is a grouping element
            if clean_label:
                file.write(f"\n{'#' * level} {clean_label}\n\n")
                if level == 2:
                    file.write("| Variabel | Tipe | Pertanyaan |\n")
                    file.write("| --- | --- | --- |\n")
        else:
            if key and clean_label and comp_type not in ['columns', 'column', 'button']:
                file.write(f"| `{key}` | `{comp_type}` | {clean_label} |\n")
                
        if 'components' in comp:
            extract_markdown(comp['components'], file, level + (1 if comp_type in [1, 'panel', 'fieldset', 'tab'] else 0))

def main():
    with open('template.json', 'r', encoding='utf-8') as f:
        template = json.load(f)
        
    with open('kamus_data_rapi.md', 'w', encoding='utf-8') as f:
        f.write("# Struktur Kuesioner FASIH\n")
        f.write("Berikut adalah susunan pertanyaan berdasarkan urutan asli (termasuk sidebar/blok) pada aplikasi pengisian:\n")
        extract_markdown(template.get('components', []), f)
        
    print("Berhasil membuat kamus_data_rapi.md")

if __name__ == "__main__":
    main()
