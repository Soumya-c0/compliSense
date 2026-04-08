import os
import sys
from ocr_engine import extract_text_with_ocr
from vector_db import add_to_regulatory_knowledge_base

def main():
    print("\n=============================================")
    print(" 🏛️ COMPLISENSE MASTER DATABASE INGESTION 🏛️ ")
    print("=============================================\n")
    
    pdf_path = input("Enter the path to the Regulatory PDF (e.g., rulebook.pdf): ").strip()
    # Remove quotes if dragged-and-dropped in powershell
    pdf_path = pdf_path.strip('\'"') 
    
    if not os.path.exists(pdf_path):
        print("❌ Error: File not found!")
        sys.exit(1)
        
    framework_name = input("Enter the Framework Name (e.g., GDPR, RBI, HIPAA): ").strip().upper()
    
    print(f"\n⚙️ Extracting text from {pdf_path} (This may take a while for scanned PDFs)...")
    text = extract_text_with_ocr(pdf_path)
    
    if "Error" in text or not text.strip():
        print(f"❌ Extraction failed or document empty.")
        sys.exit(1)
        
    print("🧠 Embedding text and writing to persistent ChromaDB...")
    status = add_to_regulatory_knowledge_base(text, framework_name)
    print(f"\n✅ {status}\n")

if __name__ == "__main__":
    main()