import json
from app.rag_engine import ComplianceRAG

rag = ComplianceRAG()

test_clause = """
The company shall retain personal data indefinitely.
"""

result = rag.analyze_clause(test_clause)

print("Compliance Analysis Result:\n")

# ✅ Option 1: Print as Pydantic model
print(result)

# ✅ Option 2: Convert to dict for JSON formatting
print(json.dumps(result.model_dump(), indent=2))

# ✅ Option 3: Access fields directly (type-safe!)
print(f"\nStatus: {result.compliance_status}")
print(f"Risk: {result.risk_level}")
print(f"Confidence: {result.confidence_score}")
print(f"Reason: {result.reason}")