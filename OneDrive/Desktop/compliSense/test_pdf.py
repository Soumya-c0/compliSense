import pdfplumber

pdf_path = "47196.pdf"

with pdfplumber.open(pdf_path) as pdf:
    full_text = ""
    for page in pdf.pages:
        full_text += page.extract_text() or ""

print("Extracted PDF Text:")
print("-------------------")
print(full_text)