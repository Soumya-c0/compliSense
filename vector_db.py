import logging
import chromadb
import json
import networkx as nx
import os
import time
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter
from groq import Groq
from dotenv import load_dotenv

# --- LOAD API KEY FROM .env ---
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- SETUP LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- GROQ MODEL CONSTANTS ---
# 70B: used for full audit reports (accuracy critical)
# 8B:  used for quick clause checks and deep queries (speed critical)
MODEL_HEAVY = "llama-3.3-70b-versatile"
MODEL_FAST  = "llama-3.1-8b-instant"

# --- INITIALIZE DATABASE & EMBEDDINGS ---
client = chromadb.PersistentClient(path="chroma_db")
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
GRAPH_PATH = "chroma_db/contract_graph.graphml"


# --- GROQ CLIENT FACTORY ---
def get_groq_client():
    """Returns a Groq client using the key from .env."""
    key = GROQ_API_KEY
    if not key:
        raise ValueError("GROQ_API_KEY not found. Please add it to your .env file.")
    return Groq(api_key=key)


# --- HELPER: SAFE JSON CLEANER ---
def clean_json_string(raw_str):
    """Strips markdown fences that some models add around JSON."""
    cleaned = raw_str.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


# --- HELPER: GROQ CHAT COMPLETION ---
def groq_complete(prompt: str, model: str, expect_json: bool = True) -> str:
    """
    Sends a prompt to Groq and returns the response text.
    If expect_json=True, instructs the model to respond only in JSON.
    """
    groq = get_groq_client()
    system_msg = (
        "You are a strict compliance analysis engine. "
        "Respond ONLY with valid JSON. No markdown, no explanation, no preamble."
        if expect_json else
        "You are a strict compliance analysis engine."
    )
    response = groq.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": prompt}
        ],
        temperature=0.1,   # Low temperature = consistent, less hallucination
        max_tokens=4096,
    )
    return response.choices[0].message.content.strip()


# ==========================================
# PHASE 1: PERMANENT MASTER REGULATORY DATABASE
# ==========================================
def add_to_regulatory_knowledge_base(text, framework_name):
    try:
        collection = client.get_or_create_collection(
            name="regulatory_frameworks", embedding_function=embedding_func
        )
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=300)
        chunks = text_splitter.split_text(text)
        if not chunks:
            return f"Error: No text found for {framework_name}."
        count = collection.count()
        collection.add(
            documents=chunks,
            metadatas=[{"framework": framework_name, "source": f"{framework_name}_chunk_{i}"} for i in range(len(chunks))],
            ids=[f"{framework_name}_id_{count + i}" for i in range(len(chunks))]
        )
        return f"Successfully embedded {len(chunks)} chunks of {framework_name} regulations."
    except Exception as e:
        return f"Error: {str(e)}"


def get_master_db_status():
    try:
        collection = client.get_collection(name="regulatory_frameworks")
        count = collection.count()
        return f"🟢 Online ({count} rules active)" if count > 0 else "🟡 Offline (Empty)"
    except Exception:
        return "🔴 Offline (Not Initialized)"


def get_available_frameworks():
    try:
        collection = client.get_collection(name="regulatory_frameworks")
        data = collection.get(include=["metadatas"])
        if data and data["metadatas"]:
            frameworks = set(
                meta.get("framework") for meta in data["metadatas"]
                if meta and "framework" in meta
            )
            return sorted(list(frameworks))
        return []
    except Exception:
        return []


def retrieve_regulatory_context(query, target_framework="ALL", n_results=3):
    """Retrieves relevant regulatory chunks from ChromaDB."""
    try:
        collection = client.get_collection(
            name="regulatory_frameworks", embedding_function=embedding_func
        )
        search_kwargs = {"query_texts": [query], "n_results": n_results}
        if target_framework != "ALL":
            search_kwargs["where"] = {"framework": target_framework}
        results = collection.query(**search_kwargs)
        if results and results['documents'] and results['documents'][0]:
            return "\n\n".join(results['documents'][0])
        return f"No specific regulation found in the {target_framework} DB."
    except ValueError:
        return "Regulatory Database is offline."
    except Exception as e:
        return f"Error retrieving regulation: {str(e)}"


# ==========================================
# PHASE 3: GRAPHRAG (RELATIONSHIP MAPPING)
# ==========================================
def build_contract_graph(text):
    """
    Uses Groq (8B model, fast) to extract entity-relationship pairs
    and builds a NetworkX graph saved to disk.
    No API key parameter needed — key comes from .env.
    """
    try:
        prompt = f"""
Extract the 15 most critical entity-relationship pairings from this contract.
Focus on: Who does What, Definitions, and Obligations.

Return ONLY a JSON array. Each item must have exactly these keys:
- "source_entity": string
- "relationship": string
- "target_entity": string

CONTRACT (first 15000 chars):
{text[:15000]}
"""
        raw = groq_complete(prompt, model=MODEL_FAST, expect_json=True)
        edges = json.loads(clean_json_string(raw))

        G = nx.DiGraph()
        for edge in edges:
            G.add_edge(
                edge["source_entity"],
                edge["target_entity"],
                relation=edge["relationship"]
            )
        os.makedirs("chroma_db", exist_ok=True)
        nx.write_graphml(G, GRAPH_PATH)
        logger.info(f"Graph built with {G.number_of_edges()} edges.")
    except Exception as e:
        logger.error(f"Graph mapping failed: {e}")


def retrieve_graph_context(query):
    if not os.path.exists(GRAPH_PATH):
        return ""
    try:
        G = nx.read_graphml(GRAPH_PATH)
        query_words = query.lower().split()
        relevant_edges = []
        for u, v, data in G.edges(data=True):
            if any(
                word in u.lower() or word in v.lower()
                for word in query_words if len(word) > 4
            ):
                relevant_edges.append(
                    f"[{u}] --({data.get('relation', 'related to')})--> [{v}]"
                )
        if relevant_edges:
            return "GRAPH RELATIONSHIPS FOUND:\n" + "\n".join(relevant_edges[:5])
        return ""
    except Exception:
        return ""


# ==========================================
# PHASE 2: TEMPORARY CONTRACT DATABASE
# ==========================================
def create_contract_knowledge_base(text, api_key=None):
    """
    api_key param kept for backward-compat with app.py but is no longer used.
    Graph is built using Groq via .env key.
    """
    try:
        try:
            client.delete_collection(name="contract_docs")
        except Exception:
            pass
        collection = client.create_collection(
            name="contract_docs", embedding_function=embedding_func
        )
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_text(text)
        if not chunks:
            return "Error: No text found in contract."
        collection.add(
            documents=chunks,
            metadatas=[{"source": f"contract_{i}"} for i in range(len(chunks))],
            ids=[f"contract_id_{i}" for i in range(len(chunks))]
        )
        # Build graph — uses Groq internally, no API key argument needed
        build_contract_graph(text)
        return f"Successfully embedded {len(chunks)} contract chunks."
    except Exception as e:
        return f"Error: {str(e)}"

def retrieve_contract_context(query, n_results=3):
    try:
        collection = client.get_collection(
            name="contract_docs", embedding_function=embedding_func
        )
        results = collection.query(query_texts=[query], n_results=n_results)
        vector_context = (
            "\n\n".join(results['documents'][0])
            if results and results['documents']
            else "No relevant clause found."
        )
        graph_context = retrieve_graph_context(query)
        if graph_context:
            return f"{vector_context}\n\n{graph_context}"
        return vector_context
    except ValueError:
        return "Contract Database not initialized."
    except Exception as e:
        return f"Error retrieving contract clause: {str(e)}"


# ==========================================
# QUERY DECOMPOSITION (fixes deep query failures)
# ==========================================
def decompose_query(user_query: str) -> dict:
    """
    Breaks a user's compliance question into structured sub-queries
    before hitting the vector store. This is the core fix for deep
    query inaccuracy — retrieval gets the RIGHT context instead of
    a fuzzy semantic match on the raw question.

    Returns a dict with:
      - clause_search_query:      what to search for in the contract DB
      - regulation_search_query:  what to search for in the regulatory DB
      - intent:                   SPECIFIC_CLAUSE_CHECK | CONTRACT_FILTERING | GAP_ANALYSIS | OTHER
    """
    prompt = f"""
You are a compliance query analyst.
Given the user's question, decompose it into precise sub-queries for retrieval.

USER QUESTION: "{user_query}"

Return ONLY a JSON object with these exact keys:
{{
  "clause_search_query": "the most precise query to find the relevant contract clause(s) in a vector database",
  "regulation_search_query": "the most precise query to find the relevant regulatory rule(s) in a regulatory vector database",
  "intent": one of ["SPECIFIC_CLAUSE_CHECK", "CONTRACT_FILTERING", "GAP_ANALYSIS", "OTHER"]
}}

Examples:
- "Is clause 4.2 compliant?" ->
  clause_search_query: "clause 4.2 text obligations"
  regulation_search_query: "regulation governing [topic of clause 4.2]"
  intent: "SPECIFIC_CLAUSE_CHECK"

- "Which clauses are non-compliant?" ->
  clause_search_query: "all data handling retention liability clauses"
  regulation_search_query: "mandatory compliance obligations data protection"
  intent: "CONTRACT_FILTERING"

- "What GDPR rules are missing?" ->
  clause_search_query: "data subject rights privacy consent breach notification"
  regulation_search_query: "GDPR mandatory articles requirements"
  intent: "GAP_ANALYSIS"
"""
    try:
        raw = groq_complete(prompt, model=MODEL_FAST, expect_json=True)
        return json.loads(clean_json_string(raw))
    except Exception as e:
        logger.warning(f"Query decomposition failed, using raw query as fallback: {e}")
        # Graceful fallback — still works, just less precise retrieval
        return {
            "clause_search_query": user_query,
            "regulation_search_query": user_query,
            "intent": "OTHER"
        }


# ==========================================
# PHASE 4: TWO-AGENT LLM-AS-A-JUDGE ENGINE
# ==========================================
CUAD_FEW_SHOT_PROMPT = """
--- EXPERT ANNOTATION EXAMPLES ---
Example (Data Retention):
Evidence A: "The Service Provider shall retain all customer telemetry data indefinitely."
Evidence B: "Personal data shall be kept for no longer than is necessary."
Output: {"clause_name": "Data Retention", "status": "NON_COMPLIANT", "risk_level": "HIGH", "confidence_score": 0.95, "reason": "Contract mandates indefinite retention, violating regulatory storage limitations."}
"""


def audit_compliance_clause(query, contract_context, regulatory_context, api_key=None):
    """
    STRICT AUTO-AUDITOR: Grades exactly one clause at a time.
    Uses MODEL_FAST (8B) — quick verdict, structured output.
    api_key param kept for backward-compat but is ignored; key comes from .env.
    """
    try:
        prompt = f"""
You are an impartial, strict Financial Compliance Judge.
Evaluate Evidence A against Evidence B based on the query.
Do NOT hallucinate rules that are not in Evidence B.
If evaluating against multiple regulatory frameworks, EXPLICITLY state which specific framework (e.g., GDPR, HIPAA, RBI) the clause violates in your 'reason'.

{CUAD_FEW_SHOT_PROMPT}

QUERY: {query}
EVIDENCE A (Contract Vector & Graph): {contract_context}
EVIDENCE B (Master Regulation): {regulatory_context}

Return ONLY a JSON object with these exact keys:
{{
  "clause_name": string,
  "status": one of ["COMPLIANT", "NON_COMPLIANT", "NEEDS_REVIEW"],
  "reason": string (detailed explanation citing specific evidence),
  "risk_level": one of ["LOW", "MEDIUM", "HIGH"],
  "confidence_score": number between 0 and 1
}}
"""
        raw = groq_complete(prompt, model=MODEL_FAST, expect_json=True)
        return clean_json_string(raw)
    except Exception as e:
        return json.dumps({"error": f"Judge Error: {str(e)}"})


def answer_deep_query(query, contract_context, regulatory_context, api_key=None):
    """
    DYNAMIC QA AGENT: Handles SPECIFIC_CLAUSE_CHECK, CONTRACT_FILTERING, GAP_ANALYSIS.
    Uses MODEL_HEAVY (70B) — deep reasoning, handles complex multi-clause questions.
    api_key param kept for backward-compat but is ignored; key comes from .env.
    """
    try:
        prompt = f"""
You are an elite Financial Compliance QA Agent.
Answer the user's Deep Query based ONLY on the provided evidence.

INTENT ROUTING — Adapt your response:
1. SPECIFIC_CLAUSE_CHECK  (e.g., "Is clause X compliant?")
   → Give a strict verdict with cited evidence.
2. CONTRACT_FILTERING     (e.g., "Which clauses are risky/non-compliant?")
   → Scan Evidence A and list ALL relevant clauses with their issues.
3. GAP_ANALYSIS           (e.g., "What GDPR rules are missing?")
   → Compare Evidence B against A. List mandatory rules from B absent from A.

QUERY: {query}

EVIDENCE A (Contract Snippets & Graph):
{contract_context}

EVIDENCE B (Master Regulation):
{regulatory_context}

Return ONLY a JSON object with these exact keys:
{{
  "detected_query_type": one of ["SPECIFIC_CLAUSE_CHECK", "CONTRACT_FILTERING", "GAP_ANALYSIS", "OTHER"],
  "comprehensive_answer": string (detailed plain-text answer, use numbered lists where helpful),
  "clauses_referenced": array of strings (specific clause names or regulatory articles cited),
  "overall_risk_level": one of ["LOW", "MEDIUM", "HIGH", "N/A"],
  "confidence_score": number between 0 and 1
}}
"""
        raw = groq_complete(prompt, model=MODEL_HEAVY, expect_json=True)
        return clean_json_string(raw)
    except Exception as e:
        return json.dumps({"error": f"QA Agent Error: {str(e)}"})


def generate_full_audit_report(full_contract_text, api_key=None, target_framework="ALL"):
    """
    Orchestrates the Two-Agent Agentic Loop.
    Agent 1 (MODEL_FAST):  Extract the 5 most critical clauses.
    Agent 2 (MODEL_HEAVY): Judge each clause against retrieved regulations.
    api_key param kept for backward-compat but is ignored; key comes from .env.
    """
    try:
        # --- AGENT 1: EXTRACTOR (fast model is sufficient for extraction) ---
        extractor_prompt = f"""
You are a legal Data Extraction Agent.
Extract the 4 most critical compliance-relevant clauses from this contract.
Do NOT evaluate them. Just extract their name and exact text.

CONTRACT TEXT (first 15000 chars):
{full_contract_text[:15000]}

Return ONLY a JSON array. Each item must have:
{{
  "clause_name": string,
  "extracted_text": string
}}
"""
        raw_extraction = groq_complete(extractor_prompt, model=MODEL_FAST, expect_json=True)
        extracted_clauses = json.loads(clean_json_string(raw_extraction))

        # --- RETRIEVAL + JUDGE LOOP (heavy model for accuracy) ---
        audit_results = []
        for clause in extracted_clauses:
            time.sleep(1.5)
            c_name = clause.get("clause_name", "Unknown")
            c_text = clause.get("extracted_text", "")

            # Retrieve targeted regulatory context for this specific clause
            law_context    = retrieve_regulatory_context(c_text, target_framework, n_results=3)
            graph_context  = retrieve_graph_context(c_text)
            combined_evidence = f"RAW TEXT:\n{c_text}\n\nGRAPH CONTEXT:\n{graph_context}"

            judge_result_str = audit_compliance_clause(
                query=f"Does this '{c_name}' clause comply with the regulations?",
                contract_context=combined_evidence,
                regulatory_context=law_context,
            )

            try:
                judge_result = json.loads(judge_result_str)
                judge_result["clause_name"] = c_name
                audit_results.append(judge_result)
            except Exception as parse_err:
                logger.warning(f"Failed to parse judge result for '{c_name}': {parse_err}")
                continue

        if not audit_results:
            return json.dumps([{"error": "Failed to generate compliance report from extracted clauses."}])

        return json.dumps(audit_results)

    except Exception as e:
        return json.dumps([{"error": f"System Pipeline Error: {str(e)}"}])