from fastapi import FastAPI
from pydantic import BaseModel
from app.rag_engine import ComplianceRAG

app = FastAPI(
    title="CompliSense API",
    description="Regulatory Compliance Automation using RAG + LLM",
    version="1.0"
)

rag_engine = ComplianceRAG()


class ClauseRequest(BaseModel):
    clause: str


@app.post("/analyze")
def analyze_clause(request: ClauseRequest):
    result = rag_engine.analyze_clause(request.clause)
    return result


@app.get("/")
def root():
    return {"message": "CompliSense API is running"}