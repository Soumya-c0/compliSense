import json
from app.ocr import extract_text
from app.preprocessing import segment_clauses


def build_regulation_dataset(pdf_path: str, regulation_name: str):
    """
    Convert regulation PDF into structured JSON dataset.
    """

    raw_text = extract_text(pdf_path)
    clauses = segment_clauses(raw_text)

    structured_data = []

    for clause in clauses:
        structured_data.append({
            "regulation": regulation_name,
            "clause_id": clause["clause_id"],
            "heading": clause["heading"],
            "text": clause["text"]
        })

    return structured_data


def save_to_json(data, output_path="data/regulations.json"):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    pdf_path = "gdpr.pdf"  # Make sure this exists in root
    regulation_name = "GDPR"

    dataset = build_regulation_dataset(pdf_path, regulation_name)
    save_to_json(dataset)

    print("Regulation dataset created successfully.")