import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
import glob
import time

def ingest_pdfs(source_dir, persist_dir):
    print("Mulai proses ingesti dokumen pedoman (RAG)...")
    
    # Kumpulkan semua file PDF secara rekursif
    pdf_files = glob.glob(os.path.join(source_dir, "**", "*.pdf"), recursive=True)
    if not pdf_files:
        print("Tidak ada file PDF ditemukan di:", source_dir)
        return
        
    documents = []
    for file in pdf_files:
        print(f"Membaca: {os.path.basename(file)}...")
        try:
            loader = PyPDFLoader(file)
            docs = loader.load()
            documents.extend(docs)
        except Exception as e:
            print(f"Gagal membaca {file}: {e}")
            
    print(f"Total {len(documents)} halaman berhasil dimuat. Mulai memecah teks...")
    
    # Chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Total {len(chunks)} chunk teks berhasil dibuat.")
    
    # Embedding menggunakan model lokal agar tidak butuh API key untuk embedding
    print("Membuat embeddings (ini mungkin memakan waktu beberapa saat)...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    vectorstore = FAISS.from_documents(chunks, embeddings)
    
    # Simpan index FAISS
    os.makedirs(persist_dir, exist_ok=True)
    vectorstore.save_local(persist_dir)
    print(f"Selesai! Vector Database berhasil disimpan di {persist_dir}")

if __name__ == "__main__":
    SOURCE_DIR = r"d:\Kantor\Code\SEJodi\monitoringKualitas\bahan"
    PERSIST_DIR = r"d:\Kantor\Code\SEJodi\monitoringKualitas\faiss_index"
    
    start_time = time.time()
    ingest_pdfs(SOURCE_DIR, PERSIST_DIR)
    print(f"Total waktu: {time.time() - start_time:.2f} detik")
