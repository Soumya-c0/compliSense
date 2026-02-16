import pytesseract
from PIL import Image
import os

# Optional: explicitly set tesseract path (ONLY if needed)
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

image_path = "test.png"

if not os.path.exists(image_path):
    print("Image not found!")
else:
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)
    print("Extracted Text:")
    print("----------------")
    print(text)