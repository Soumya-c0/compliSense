from app.embeddings import RegulationVectorStore

print("Running Phase 4 test...")

store = RegulationVectorStore()
store.load_regulations("data/regulations.json")

query = "Personal data must be processed lawfully"

results = store.search(query, top_k=2)

print("\nTop Matches:")
for r in results:
    print(f"{r['clause_id']} - {r['text'][:120]}")
    print("------")