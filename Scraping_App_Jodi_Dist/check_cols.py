import pandas as pd
df = pd.read_parquet('jodi_detail_assignment_20260714_092652.parquet')
cols = [c for c in df.columns if 'nama' in str(c).lower() or 'kk' in str(c).lower() or 'kepala' in str(c).lower()]
for c in cols: print(c)
