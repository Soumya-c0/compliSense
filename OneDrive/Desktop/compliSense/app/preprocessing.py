import re
from typing import List, Dict


def clean_ocr_text(text: str) -> str:
    """
    Remove OCR noise while preserving structure.
    """

    # Remove URLs
    text = re.sub(r'http\S+', '', text)

    # Remove excessive spaces but keep line breaks
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n', text)

    # Remove common GDPR footer/header patterns
    text = re.sub(r'EUR-Lex.*', '', text)
    text = re.sub(r'EN\s*$', '', text)

    text = text.replace(" ,", ",").replace(" .", ".")

    return text.strip()


def detect_headings(lines: List[str]) -> List[Dict]:
    clauses = []
    current_article = None
    current_clause_number = None
    current_text = []

    article_pattern = re.compile(r'^Article\s+(\d+)', re.IGNORECASE)
    numbered_pattern = re.compile(r'^(\d+)\.')

    for line in lines:
        line = line.strip()

        if not line:
            continue

        article_match = article_pattern.match(line)
        numbered_match = numbered_pattern.match(line)

        # Detect Article
        if article_match:
            # Save previous clause
            if current_article and current_clause_number and current_text:
                clauses.append({
                    "clause_id": f"Article_{current_article}_{current_clause_number}",
                    "heading": f"Article {current_article} - Clause {current_clause_number}",
                    "text": " ".join(current_text).strip()
                })

            current_article = article_match.group(1)
            current_clause_number = None
            current_text = []
            continue

        # Detect numbered clause inside article
        if numbered_match and current_article:
            # Save previous clause
            if current_clause_number and current_text:
                clauses.append({
                    "clause_id": f"Article_{current_article}_{current_clause_number}",
                    "heading": f"Article {current_article} - Clause {current_clause_number}",
                    "text": " ".join(current_text).strip()
                })

            current_clause_number = numbered_match.group(1)
            current_text = []
            continue

        # Add text
        if current_clause_number:
            current_text.append(line)

    # Save last clause
    if current_article and current_clause_number and current_text:
        clauses.append({
            "clause_id": f"Article_{current_article}_{current_clause_number}",
            "heading": f"Article {current_article} - Clause {current_clause_number}",
            "text": " ".join(current_text).strip()
        })

    return clauses


def segment_clauses(raw_text: str) -> List[Dict]:
    """
    Full pipeline: clean text and segment into structured clauses.
    """
    cleaned = clean_ocr_text(raw_text)
    lines = cleaned.split("\n")

    clauses = detect_headings(lines)

    return clauses