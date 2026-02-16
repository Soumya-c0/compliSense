import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import os


# Optional: uncomment if tesseract path issue
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_text_from_pdf(pdf_path):
    """
    Extract text from normal (non-scanned) PDFs.
    """
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"

    return text.strip()


def extract_text_from_scanned_pdf(pdf_path):
    """
    Extract text from scanned PDFs using OCR.
    """
    text = ""
    images = convert_from_path(pdf_path)

    for image in images:
        text += pytesseract.image_to_string(image) + "\n"

    return text.strip()


def extract_text(pdf_path):
    """
    Automatically detect if PDF is scanned or normal.
    """
    text = extract_text_from_pdf(pdf_path)

    if len(text) < 50:  # If too little text, assume scanned
        print("Detected scanned PDF. Running OCR...")
        text = extract_text_from_scanned_pdf(pdf_path)

    return text