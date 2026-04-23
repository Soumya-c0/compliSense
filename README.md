# Fin-Audit | Enterprise Compliance Engine

An AI-driven compliance auditing system designed to ingest complex legal contracts and cross-reference them against master regulatory frmeworks (such as RBI, GDPR and HIPAA) in real-time. This system utilizes a decoupled Two-Agent LLM pipeline and GraphRAG to guarantee hallucination-free audits while operating on open-source inference engines.

## Key Features

* **Two-Agent Pipeline:** Agent 1 (Fast Extractor) isolates relevant clauses without judgment, while Agent 2 (Strict Judge) evaluates compliance, preventing context-window overload and reducing hallucinations.
* **GraphRAG Integration:** Combines standard Vector Search (ChromaDB) with Entity Relationship Mapping (NetworkX) to track complex "who-does-what" dependencies across multi-page documents.
* **Dynamic Intent Routing:** Automatically decomposes user queries to accurately route specific clause checks or performs broad gap analysis to the appropriate reasoning models.
* **Open-Source Inference:** Powered by Llama-3 models via Groq LPUs.
* **Auditable Reporting:** Generates downloadable PDF reports with explicit confidence scores, visual risk indicators and clear evidence trails for human review.

## Technology Stack

* **Frontend:** Streamlit, PyVis 
* **AI & Inference:** Groq API, Llama-3.3-70b-versatile, Llama-3.1-8b-instant
* **Vector Database:** ChromaDB (all-MiniLM-L6-v2 Embeddings)
* **Graph Database:** NetworkX
* **Document Processing:** OCR Engine, LangChain Text Splitters

## Installation & Local Setup

1. **Clone the repository:**
   ```bash
   git clone
   cd complisense
2. **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    # On Windows:
    venv\Scripts\activate
    # On Mac/Linux:
    source venv/bin/activate
3. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
4. **Environment Variables:**
    Create a .env file in the root directory and add your Groq API key:
    ```code snippet
    GROQ_API_KEY=api_key_here
5. **Run the Application:**
    ```bash
    streamlit run app.py
## Security & Privacy
This application is designed with enterprise data privacy in mind. Contracts and regulatory master documents are embedded locally in ChromaDB and NetworkX. Prompts sent to external inference endpoints are strictly scoped to the targeted clauses to minimize data exposure.

## **Live Demo**

Try the application here :- https://finaudit-aj9scmhuwmu8jpoukw4glg.streamlit.app/
