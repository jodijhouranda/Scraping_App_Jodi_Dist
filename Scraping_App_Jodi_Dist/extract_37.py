import pandas as pd

df = pd.read_excel('Template Jodi.xlsx')
# drop 'submit', 'draf', 'total' if they exist to clean it up a bit if needed
row = df.iloc[36]
print("--- 37th SLS ---")
print(row.to_dict())

# Let's save a temp template with only this row for testing
df_test = pd.DataFrame([row])
df_test.to_excel('Template_Test_37.xlsx', index=False)
print("Saved to Template_Test_37.xlsx")
