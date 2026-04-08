import google.generativeai as genai

# Put your actual API key here
genai.configure(api_key="AIzaSyDgOGpV0OV-QqeXA4DMzTroC3zWUQJbOKw")

print("Available Models for Text Generation:")
print("-" * 40)
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
print("-" * 40)