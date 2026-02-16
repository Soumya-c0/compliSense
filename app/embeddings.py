import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


class RegulationVectorStore:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.metadata = []

    def load_regulations(self, json_path="data/regulations.json"):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        texts = [item["text"] for item in data]
        self.metadata = data

        embeddings = self.model.encode(texts, convert_to_numpy=True)

        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)

        print(f"Loaded {len(texts)} regulation clauses into vector store.")

    def search(self, query_text, top_k=2):
        query_embedding = self.model.encode([query_text], convert_to_numpy=True)

        distances, indices = self.index.search(query_embedding, top_k)

        results = []
        for idx in indices[0]:
            results.append(self.metadata[idx])

        return results