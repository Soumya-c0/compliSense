import gc
import json
import re
import ollama
from app.embeddings import RegulationVectorStore
from app.schemas import ComplianceResult
from pydantic import ValidationError


class ComplianceRAG:
    def __init__(self):
        self.vector_store = RegulationVectorStore()
        self.vector_store.load_regulations("data/regulations.json")

    def analyze_clause(self, clause_text: str) -> ComplianceResult:
        """
        Analyzes a contract clause for GDPR compliance using RAG + LLM.
        
        Returns:
            ComplianceResult: Validated Pydantic model with guaranteed schema compliance
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

        # ✅ IMPROVED PROMPT - Added explicit scoring guidance
        prompt = f"""You are a JSON generator. Output ONLY valid JSON. No other text.

Contract Clause: {clause_text}

GDPR Rules: {regulation_context}

IMPORTANT SCORING RULES:
- If clause violates GDPR (e.g., "indefinitely", "forever", "no time limit"): confidence_score should be HIGH (0.8-0.95) because you're CONFIDENT it's NON-COMPLIANT
- If clause complies with GDPR: confidence_score should be HIGH (0.8-0.95) because you're CONFIDENT it's COMPLIANT
- Only use LOW confidence (0.3-0.5) if you're UNSURE about compliance

VIOLATIONS:
- "Indefinitely", "forever", "permanently" = Non-Compliant, High Risk
- "No retention limit", "keep all data" = Non-Compliant, High Risk

Output this exact JSON format:
{{
  "compliance_status": "Compliant" or "Non-Compliant" or "Partially Compliant" or "Unknown",
  "reason": "brief explanation of why it does or does not comply (minimum 5 characters)",
  "risk_level": "Low" or "Medium" or "High" or "Unknown",
  "confidence_score": number between 0.0 and 1.0
}}

JSON:"""

        try:
            # ✅ Call LLM with JSON format enforcement
            response = ollama.chat(
                model="tinyllama",
                messages=[{"role": "user", "content": prompt}],
                format="json",
            )

            response_text = response["message"]["content"]
            
            # ✅ Extract and validate with Pydantic
            result = self._extract_and_validate_json(response_text)
            
            # ✅ Apply rule-based overrides for critical violations
            result = self._apply_rule_based_checks(clause_text, result)
            
            return result

        except Exception as e:
            # Return fallback with Pydantic validation
            return ComplianceResult(
                compliance_status="Unknown",
                reason=f"Analysis failed due to technical error: {str(e)}",
                risk_level="Unknown",
                confidence_score=0.0
            )

    def _apply_rule_based_checks(self, clause_text: str, result: ComplianceResult) -> ComplianceResult:
        """
        Apply rule-based overrides for known critical GDPR violations.
        This acts as a safety net for cases where the LLM might misjudge.
        
        Args:
            clause_text: Original contract clause
            result: LLM-generated result
            
        Returns:
            ComplianceResult: Corrected result if rules triggered
        """
        
        clause_lower = clause_text.lower()
        
        # 🔥 RULE 1: Indefinite data retention violations
        indefinite_keywords = [
            "indefinitely", 
            "indefinite", 
            "forever", 
            "permanently",
            "no retention limit",
            "retain all data",
            "keep all data",
            "without time limit",
            "no expiration",
            "never delete"
        ]
        
        if any(keyword in clause_lower for keyword in indefinite_keywords):
            # Override to Non-Compliant
            result.compliance_status = "Non-Compliant"
            result.risk_level = "High"
            result.reason = "Indefinite data retention violates GDPR storage limitation principle (Article 5(1)(e))."
            result.confidence_score = max(result.confidence_score, 0.85)
        
        # 🔥 RULE 2: Third-party sharing without consent
        sharing_keywords = [
            "share with third parties without consent",
            "sell personal data",
            "transfer data without permission"
        ]
        
        if any(keyword in clause_lower for keyword in sharing_keywords):
            result.compliance_status = "Non-Compliant"
            result.risk_level = "High"
            result.reason = "Sharing personal data without consent violates GDPR lawfulness principle (Article 6)."
            result.confidence_score = max(result.confidence_score, 0.85)
        
        # 🔥 RULE 3: No data subject rights
        rights_violations = [
            "users cannot delete their data",
            "no right to deletion",
            "data cannot be removed",
            "users cannot access their data"
        ]
        
        if any(keyword in clause_lower for keyword in rights_violations):
            result.compliance_status = "Non-Compliant"
            result.risk_level = "High"
            result.reason = "Denying data subject rights violates GDPR Articles 15-22 (right to access, deletion, etc.)."
            result.confidence_score = max(result.confidence_score, 0.85)
        
        return result

    def _extract_and_validate_json(self, response_text: str) -> ComplianceResult:
        """
        Extracts JSON from LLM response and validates it with Pydantic.
        Auto-corrects minor issues and guarantees schema compliance.
        
        Args:
            response_text: Raw text from LLM
            
        Returns:
            ComplianceResult: Validated Pydantic model
        """
        
        # Try to find JSON object in the response
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
        
        if not json_match:
            # Fallback: No JSON found
            return ComplianceResult(
                compliance_status="Unknown",
                reason="LLM did not return structured output",
                risk_level="Unknown",
                confidence_score=0.0
            )
        
        try:
            # Parse the JSON
            raw_json = json.loads(json_match.group())
            
            # ✅ AUTO-CORRECT: Clean up the reason field
            if "reason" in raw_json:
                raw_json["reason"] = raw_json["reason"].strip()
                # If reason is too short, add context
                if len(raw_json["reason"]) < 5:
                    raw_json["reason"] = "Compliance analysis: " + raw_json["reason"]
            
            # ✅ AUTO-CORRECT: Normalize compliance_status values
            if "compliance_status" in raw_json:
                status = raw_json["compliance_status"].strip()
                # Handle common variations
                if status.lower() in ["compliant", "yes", "pass"]:
                    raw_json["compliance_status"] = "Compliant"
                elif status.lower() in ["non-compliant", "noncompliant", "no", "fail"]:
                    raw_json["compliance_status"] = "Non-Compliant"
                elif status.lower() in ["partial", "partially compliant", "partly"]:
                    raw_json["compliance_status"] = "Partially Compliant"
            
            # ✅ AUTO-CORRECT: Normalize risk_level values
            if "risk_level" in raw_json:
                risk = raw_json["risk_level"].strip().lower()
                if risk in ["low", "l"]:
                    raw_json["risk_level"] = "Low"
                elif risk in ["medium", "med", "m", "moderate"]:
                    raw_json["risk_level"] = "Medium"
                elif risk in ["high", "h", "critical"]:
                    raw_json["risk_level"] = "High"
            
            # ✅ VALIDATE with Pydantic - This enforces all schema rules
            return ComplianceResult(**raw_json)
            
        except ValidationError as e:
            # Pydantic validation failed - return fallback with error details
            error_details = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
            return ComplianceResult(
                compliance_status="Unknown",
                reason=f"Validation failed: {error_details}",
                risk_level="Unknown",
                confidence_score=0.0
            )
            
        except json.JSONDecodeError as e:
            # JSON parsing failed
            return ComplianceResult(
                compliance_status="Unknown",
                reason=f"Invalid JSON format: {str(e)}",
                risk_level="Unknown",
                confidence_score=0.0
            )