import json, re, html

TYPE_MAP = {
    1: 'BLOK/PANEL',
    2: 'Tabel (Datagrid)',
    3: 'Teks HTML (Info)',
    4: 'Angka/Tersembunyi',
    5: 'Pilihan (Select)',
    6: 'Tombol (Radio)',
    20: 'Isian Angka (Rupiah)',
    21: 'Tabel Isian',
    24: 'Isian Angka',
    25: 'Pilihan Dropdown',
    26: 'Pilihan Dropdown',
    27: 'Pilihan Dropdown',
    28: 'Isian Angka',
    29: 'Slider/Angka',
    30: 'Isian Teks Panjang',
    32: 'Upload Foto',
    33: 'Geotag/GPS',
    35: 'Waktu (Datetime)',
    36: 'Tanda Tangan',
}

def clean_label(label):
    if not isinstance(label, str):
        return ''
    s = re.sub(r'<style.*?</style>', '', label, flags=re.DOTALL)
    s = re.sub(r'<script.*?</script>', '', s, flags=re.DOTALL)
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def walk(node, results, section="", subsection=""):
    if isinstance(node, list):
        for item in node:
            walk(item, results, section, subsection)
        return
    
    if not isinstance(node, dict):
        return
    
    ntype = node.get('type', '')
    label = clean_label(node.get('label', ''))
    key = node.get('dataKey', '') or node.get('key', '')
    
    if ntype == 1:
        section = label
        results.append({
            'kind': 'section',
            'section': section,
            'key': key,
            'label': label,
            'type': '',
            'contoh': ''
        })
    elif isinstance(ntype, int) and ntype != 3:  # skip HTML info (type 3)
        readable_type = TYPE_MAP.get(ntype, f'Tipe {ntype}')
        if key:
            results.append({
                'kind': 'field',
                'section': section,
                'key': key,
                'label': label if label else f'({key})',
                'type': readable_type,
                'contoh': ''
            })
    
    for child_key in ['components', 'columns', 'rows']:
        if child_key in node:
            walk(node[child_key], results, section, subsection)

def main():
    with open('template.json', encoding='utf-8') as f:
        template = json.load(f)
    
    results = []
    walk(template.get('components', []), results)
    
    # Load actual API answers for cross-reference
    with open('klik_api_log.json', encoding='utf-8') as f:
        api_log = json.load(f)
    
    api_keys = [k for k in api_log.keys() if 'get-by-assignment-id' in k]
    api_answers = {}
    if api_keys:
        data = api_log[api_keys[0]].get('data', {})
        data_inner = json.loads(data['data']) if isinstance(data.get('data'), str) else data.get('data', {})
        if isinstance(data_inner, dict):
            for ans in data_inner.get('answers', []):
                dk = ans.get('dataKey', '')
                val = ans.get('answer', '')
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                val = str(val)
                if len(val) > 60:
                    val = val[:57] + '...'
                api_answers[dk] = val
    
    # Enrich with API answer examples
    for r in results:
        if r['kind'] == 'field':
            r['contoh'] = api_answers.get(r['key'], '')
    
    # Filter: skip purely internal/hidden variables that don't correspond to real questions
    internal_prefixes = ['ec_', 'set_', 'cek', 'html', 'result_', 'var_', 'msg_', 'info_total']
    
    # Generate clean markdown output
    with open('Kamus_Variabel_Final.md', 'w', encoding='utf-8') as f:
        f.write("# 📋 Kamus Variabel Kuesioner SE2026 – FASIH BPS\n\n")
        f.write("Pemetaan **variabel API** ↔ **pertanyaan kuesioner asli**, disusun per blok.\n\n")
        f.write("> Di file Excel hasil scraping, variabel muncul dengan prefix:\n")
        f.write("> - **`ans_`** → Jawaban PPL (data aktual hasil pendataan)\n")
        f.write("> - **`pre_`** → Data prelist (data awal sebelum didata)\n\n")
        f.write("---\n\n")
        
        current_section = ""
        field_no = 0
        
        for r in results:
            if r['kind'] == 'section':
                current_section = r['label']
                field_no = 0
                f.write(f"\n---\n\n## 📁 {r['label']}\n\n")
                f.write("| No | Variabel | Tipe Input | Pertanyaan / Keterangan | Contoh Isian |\n")
                f.write("|:--:|----------|:----------:|------------------------|-------------|\n")
            elif r['kind'] == 'field':
                # Skip pure enabling conditions and internal vars
                is_internal = any(r['key'].startswith(p) for p in internal_prefixes)
                if is_internal and not r['contoh']:
                    continue  # Skip internal vars with no data
                    
                field_no += 1
                contoh = r['contoh'].replace('|', '∣').replace('\n', ' ')
                label = r['label'].replace('|', '∣').replace('\n', ' ')
                f.write(f"| {field_no} | `{r['key']}` | {r['type']} | {label} | {contoh} |\n")
        
        f.write("\n\n---\n")
        f.write("*Dokumen ini diekstrak otomatis dari API Template Designer FASIH BPS.*\n")
    
    fields = [r for r in results if r['kind'] == 'field']
    sections = [r for r in results if r['kind'] == 'section']
    print(f"Berhasil: {len(sections)} blok, {len(fields)} variabel")
    print(f"Output: Kamus_Variabel_Final.md")

if __name__ == "__main__":
    main()
