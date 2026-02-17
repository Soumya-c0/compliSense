import json
from app.rag_engine import ComplianceRAG

rag = ComplianceRAG()

test_clause = """
The company shall retain personal data indefinitely.
"""

result = rag.analyze_clause(test_clause)

print("Compliance Analysis Result:\n")
print(json.dumps(result, indent=2))