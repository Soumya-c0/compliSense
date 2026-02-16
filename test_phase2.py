from app.ocr import extract_text
from app.preprocessing import segment_clauses

pdf_path = "gdpr.pdf"

raw_text = extract_text(pdf_path)

clauses = segment_clauses(raw_text)

print("Total Clauses Detected:", len(clauses))
print("\nFirst 2 Clauses:\n")

for clause in clauses[:2]:
    print(clause)
    print("--------------------------------------------------")
