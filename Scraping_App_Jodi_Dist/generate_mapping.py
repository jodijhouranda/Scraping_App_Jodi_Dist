import json
import pandas as pd

def extract_components(components, mapping, parent_label=""):
    for comp in components:
        if isinstance(comp, list):
            extract_components(comp, mapping, parent_label)
            continue
            
        key = comp.get('dataKey', '')
        if not key:
            key = comp.get('key', '')
        label = comp.get('label', '')
        comp_type = comp.get('type', '')
        
        # Clean up html tags from label
        import re
        clean_label = re.sub('<[^<]+>', '', label).strip() if isinstance(label, str) else ''
        
        if key and comp_type not in ['panel', 'columns', 'column', 'well', 'fieldset', 'button']:
            full_label = f"{parent_label} > {clean_label}" if parent_label else clean_label
            mapping.append({
                'Variabel (Key)': key,
                'Tipe': comp_type,
                'Pertanyaan (Label)': full_label
            })
            
        # Recursive call for nested components
        if 'components' in comp:
            new_parent = clean_label if comp_type in ['panel', 'fieldset', 'datagrid', 'editgrid'] else parent_label
            extract_components(comp['components'], mapping, new_parent)
            
        # Handling columns
        if 'columns' in comp:
            for col in comp['columns']:
                if 'components' in col:
                    extract_components(col['components'], mapping, parent_label)

def main():
    with open('template.json', 'r', encoding='utf-8') as f:
        template = json.load(f)
        
    mapping = []
    extract_components(template.get('components', []), mapping)
    
    df = pd.DataFrame(mapping)
    df.to_excel('Kamus_Data_Kuesioner.xlsx', index=False)
    
    # Also save as markdown table for quick view
    with open('kamus_data.md', 'w', encoding='utf-8') as f:
        f.write("# Mapping Variabel Kuesioner\n\n")
        f.write("| Variabel (Key) | Tipe | Pertanyaan (Label) |\n")
        f.write("| --- | --- | --- |\n")
        for m in mapping:
            f.write(f"| `{m['Variabel (Key)']}` | {m['Tipe']} | {m['Pertanyaan (Label)']} |\n")
            
    print(f"Berhasil mengekstrak {len(mapping)} variabel.")

if __name__ == "__main__":
    main()
