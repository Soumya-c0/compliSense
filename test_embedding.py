from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

text = "Personal data shall be retained for only as long as necessary."

embedding = model.encode(text)

print("Embedding length:", len(embedding))
print("First 5 values:", embedding[:5])