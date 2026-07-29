import os
import glob
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
import certifi

def main():
    print("Memeriksa kredensial database TiDB di .env...")
    load_dotenv()
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "4000")
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASS")
    db_name = os.getenv("DB_NAME")
    
    if not (db_host and db_user and db_pass and db_pass != "MASUKKAN_PASSWORD_DISINI"):
        print("Kredensial belum diisi lengkap di .env. Silakan isi terlebih dahulu.")
        return
        
    print(f"Kredensial ditemukan untuk host: {db_host}")
    
    # Cari folder terbaru di result
    result_dir = "result"
    if not os.path.exists(result_dir):
        print(f"Folder {result_dir}/ tidak ditemukan!")
        return
        
    subdirs = [os.path.join(result_dir, d) for d in os.listdir(result_dir) if os.path.isdir(os.path.join(result_dir, d))]
    if not subdirs:
        print(f"Tidak ada folder hasil di {result_dir}/")
        return
        
    latest_dir = max(subdirs, key=os.path.getctime)
    print(f"\nMenggunakan hasil terbaru dari: {latest_dir}")
    
    # Deteksi file CSV di folder tersebut
    csv_files = glob.glob(os.path.join(latest_dir, "*.csv"))
    if not csv_files:
        print("Tidak ada file CSV di folder tersebut.")
        return
        
    # Dictionary mapping nama tabel ke file
    table_files = {}
    for f in csv_files:
        basename = os.path.basename(f)
        if "Rekap_PCL.csv" in basename:
            table_files['rekap_pcl'] = f
        elif "Kinerja_PPL.csv" in basename:
            table_files['kinerja_ppl'] = f
        elif "Template_Wilayah.csv" in basename:
            table_files['template_wilayah'] = f
        elif "Data_Usaha.csv" in basename:
            table_files['data_usaha'] = f
        elif "Detail_Data.csv" in basename:
            table_files['detail_data'] = f
        elif "Error_Log.csv" in basename:
            table_files['error_log'] = f
            
    if not table_files:
        print("Tidak ditemukan file CSV yang sesuai (Rekap_PCL, Data_Usaha, dll).")
        return
        
    try:
        ca_path = certifi.where()
        print(f"Mengunggah tabel ke database {db_name} di {db_host}...")
        
        db_url = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?ssl_ca={ca_path}&ssl_verify_cert=true&ssl_verify_identity=true"
        engine = create_engine(db_url)
        
        for table_name, file_path in table_files.items():
            print(f"  Upload {table_name} dari {os.path.basename(file_path)}...")
            df = pd.read_csv(file_path, low_memory=False)
            df.to_sql(table_name, con=engine, if_exists='replace', index=False)
            
        print("\nBerhasil mengunggah semua tabel ke TiDB!")
    except Exception as e:
        print(f"Gagal mengunggah ke TiDB: {e}")

if __name__ == "__main__":
    main()
