import json
import pandas as pd
import os

dir_path = r"D:\Kantor\Code\SEJodi\monitoringKualitas"

with open(os.path.join(dir_path, 'var_options.json'), 'r', encoding='utf-8') as f:
    var_options = json.load(f)

TYPE_MAP = {
    1: "Blok / Panel",
    4: "Angka / Tersembunyi",
    6: "Isian Teks Panjang",
    8: "Upload Foto",
    13: "Isian Teks Pendek",
    14: "Isian Angka",
    19: "Datetime / Waktu",
    21: "Geotag / GPS",
    25: "Isian Angka",
    26: "Pilihan Radio",
    30: "Pilihan Dropdown",
    33: "Geotag / GPS",
    35: "Upload File",
    99: "Lainnya"
}

def is_real_question(var_key, var_def):
    label = var_def.get("question", "")
    skip_signals = ['<style', '{', '.se-header', 'SE2026 - L', 'SE2026 - P',
                    'Default / Light Theme', '$style', '[id^=', '.blok-hea', '#set_nik']
    if any(s in label for s in skip_signals):
        return False
    if var_def.get("type") == 1 and not var_def.get("options"):
        return False
    return True

rows = []
for var_key, var_def in var_options.items():
    if not is_real_question(var_key, var_def):
        continue
    
    label = var_def.get("question", "")
    v_type = var_def.get("type", 0)
    type_str = TYPE_MAP.get(v_type, f"Tipe {v_type}")
    options = var_def.get("options", [])
    options_str = " | ".join([f"{o.get('value')}: {o.get('label')}" for o in options]) if options else ""
    
    rows.append({
        "Variabel API (Mesin)": var_key,
        "Kolom Dataset ans_": f"ans_{var_key}",
        "Kolom Dataset pre_": f"pre_{var_key}",
        "Pertanyaan Asli": label,
        "Tipe Input": type_str,
        "Pilihan Jawaban": options_str,
        "Jumlah Pilihan": len(options) if options else 0
    })

df_bridge = pd.DataFrame(rows)
print(f"Total variabel real: {len(df_bridge)}")
print(f"  - Ada pilihan    : {len(df_bridge[df_bridge['Jumlah Pilihan'] > 0])}")
print(f"  - Isian bebas    : {len(df_bridge[df_bridge['Jumlah Pilihan'] == 0])}")

excel_path = os.path.join(dir_path, "Kamus_Bridging.xlsx")
with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
    df_bridge.to_excel(writer, sheet_name="Variabel Mapping", index=False)
    
    df_opt = df_bridge[df_bridge['Jumlah Pilihan'] > 0].copy()
    df_opt.to_excel(writer, sheet_name="Variabel Pilihan", index=False)
    
    option_rows = []
    for var_key, var_def in var_options.items():
        if not is_real_question(var_key, var_def):
            continue
        for opt in var_def.get("options", []):
            option_rows.append({
                "Variabel": var_key,
                "Pertanyaan": var_def.get("question", "")[:80],
                "Nilai (Value)": opt.get("value"),
                "Label Pilihan": opt.get("label")
            })
    if option_rows:
        pd.DataFrame(option_rows).to_excel(writer, sheet_name="Detail Pilihan", index=False)

print(f"Excel disimpan: {excel_path}")

# JSON untuk app.py
bridge_json = {}
for _, row in df_bridge.iterrows():
    vk = row["Variabel API (Mesin)"]
    bridge_json[vk] = {
        "question": row["Pertanyaan Asli"],
        "type_str": row["Tipe Input"],
        "options": var_options.get(vk, {}).get("options", [])
    }

json_path = os.path.join(dir_path, "Kamus_Bridging.json")
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(bridge_json, f, ensure_ascii=False, indent=2)
print(f"JSON disimpan: {json_path}")
