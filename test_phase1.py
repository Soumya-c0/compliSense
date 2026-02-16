from app.ocr import extract_text

pdf_path = "47196.pdf"

text = extract_text(pdf_path)

print("Extracted Text:")
print("--------------------")
print(text[:500])  # Print first 500 chars