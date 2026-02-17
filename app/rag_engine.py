import gc
import json
import re
import ollama
from app.embeddings import RegulationVectorStore


class ComplianceRAG:
    def __init__(self):
        self.vector_store = RegulationVectorStore()
        self.vector_store.load_regulations("data/regulations.json")

    def analyze_clause(self, clause_text: str):
        """
        Analyzes a contract clause for GDPR compliance using RAG + LLM.
        
        Returns:
            dict: Structured compliance JSON with status, reason, risk_level, and confidence_score
        """
        
        # Step 1: Retrieve relevant regulation clauses
        retrieved = self.vector_store.search(clause_text, top_k=2)

        regulation_context = "\n\n".join(
            [f"{r['clause_id']}: {r['text']}" for r in retrieved]
        )

        # 🔥 Free embedding model memory before loading LLM
        if hasattr(self.vector_store, "model"):
            del self.vector_store.model
        gc.collect()

        # ✅ IMPROVED PROMPT - More concise, clearer JSON requirements
        prompt = f"""You are a JSON generator. Output ONLY valid JSON. No other text.

Contract Clause: {clause_text}

GDPR Rules: {regulation_context}

Analyze if the contract clause complies with GDPR rules.

Output this exact JSON format:
{{
  "compliance_status": "Compliant" or "Non-Compliant",
  "reason": "brief explanation of why it does or does not comply",
  "risk_level": "Low" or "Medium" or "High",
  "confidence_score": number between 0.0 and 1.0
}}

JSON:"""

        try:
            # ✅ Added format="json" to force JSON output (if Ollama version supports it)
            response = ollama.chat(
                model="tinyllama",
                messages=[{"role": "user", "content": prompt}],
                format="json",  # Forces JSON output in newer Ollama versions
            )

            response_text = response["message"]["content"]
            
            # ✅ ROBUST JSON EXTRACTION - Handles cases where LLM adds extra text
            return self._extract_and_validate_json(response_text)

        except Exception as e:
            return {
                "error": f"LLM Error: {str(e)}",
                "compliance_status": "Unknown",
                "reason": "Analysis failed due to technical error",
                "risk_level": "Unknown",
                "confidence_score": 0.0
            }

    def _extract_and_validate_json(self, response_text: str) -> dict:
        """
        Extracts and validates JSON from LLM response.
        Handles cases where the LLM adds extra text before/after JSON.
        
        Args:
            response_text: Raw text from LLM
            
        Returns:
            dict: Validated compliance JSON or error dict
        """
        
        # Try to find JSON object in the response
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
        
        if not json_match:
            return {
                "error": "No JSON found in LLM output",
                "raw_output": response_text,
                "compliance_status": "Unknown",
                "reason": "LLM did not return structured output",
                "risk_level": "Unknown",
                "confidence_score": 0.0
            }
        
        try:
            # Parse the JSON
            result = json.loads(json_match.group())
            
            # ✅ VALIDATE required fields exist
            required_fields = ["compliance_status", "reason", "risk_level", "confidence_score"]
            missing_fields = [field for field in required_fields if field not in result]
            
            if missing_fields:
                return {
                    "error": f"Missing required fields: {missing_fields}",
                    "raw_output": response_text,
                    "compliance_status": result.get("compliance_status", "Unknown"),
                    "reason": result.get("reason", "Incomplete analysis"),
                    "risk_level": result.get("risk_level", "Unknown"),
                    "confidence_score": result.get("confidence_score", 0.0)
                }
            
            # ✅ VALIDATE field values
            if result["compliance_status"] not in ["Compliant", "Non-Compliant"]:
                result["compliance_status"] = "Unknown"
            
            if result["risk_level"] not in ["Low", "Medium", "High"]:
                result["risk_level"] = "Unknown"
            
            # Ensure confidence_score is a float between 0 and 1
            try:
                score = float(result["confidence_score"])
                result["confidence_score"] = max(0.0, min(1.0, score))
            except (ValueError, TypeError):
                result["confidence_score"] = 0.0
            
            return result
            
        except json.JSONDecodeError as e:
            return {
                "error": f"Invalid JSON format: {str(e)}",
                "raw_output": response_text,
                "compliance_status": "Unknown",
                "reason": "JSON parsing failed",
                "risk_level": "Unknown",
                "confidence_score": 0.0
            }