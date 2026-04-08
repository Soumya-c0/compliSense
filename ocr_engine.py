import fitz  # PyMuPDF
import sys
import types
import os
import streamlit as st

# --- THE HACKATHON SHIM ---
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

sys.modules["langchain.docstore"] = types.ModuleType("langchain.docstore")
m1 = types.ModuleType("langchain.docstore.document")
m1.Document = Document
sys.modules["langchain.docstore.document"] = m1

m2 = types.ModuleType("langchain.text_splitter")
m2.RecursiveCharacterTextSplitter = RecursiveCharacterTextSplitter
sys.modules["langchain.text_splitter"] = m2
# --------------------------

from paddleocr import PaddleOCR
import numpy as np

@st.cache_resource
def get_ocr_model():
    print("Loading PaddleOCR model into memory...")
    # Turned off angle_cls here for speed and stability
    return PaddleOCR(use_angle_cls=False, lang='en')

def extract_text_with_ocr(pdf_path):
    """Smart Extraction: Reads digital PDFs instantly, uses OCR for scanned images."""
    text_result = ""
    
    try:
        ocr = get_ocr_model()
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            
            # --- ENTERPRISE SMART ROUTING ---
            # 1. Try to read the text digitally first (Lightning Fast!)
            direct_text = page.get_text()
            
            if len(direct_text.strip()) > 50:
                # If it found digital text, use it and skip OCR for this page!
                text_result += f"\n\n--- Page {page_num + 1} ---\n\n"
                text_result += direct_text
                continue 
            
            # 2. If no text is found, it must be a scanned image. Turn on PaddleOCR!
            zoom = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=zoom, alpha=False, colorspace=fitz.csRGB)
            
            temp_img_path = f"temp_page_{page_num}.png"
            pix.save(temp_img_path)
            
            result = ocr.ocr(temp_img_path)
            text_result += f"\n\n--- Page {page_num + 1} (OCR Mode) ---\n\n"
            
            if result and result[0]:
                for line in result[0]:
                    text = line[1][0]  
                    text_result += text + "\n"
                    
            if os.path.exists(temp_img_path):
                os.remove(temp_img_path)
                
        return text_result

    except Exception as e:
        return f"OCR Error: {str(e)}"