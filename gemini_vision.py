import google.generativeai as genai
import requests
from io import BytesIO
from PIL import Image
import os

# Gemini config
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def upload_to_gemini(img_path, mime_type="image/png"):
    file = genai.upload_file(img_path, mime_type=mime_type)
    return file

def extract_total_from_receipt(receipt_url):
    try:
        response = requests.get(receipt_url)
        img = Image.open(BytesIO(response.content)).convert("RGB")
        temp_img_path = "/tmp/receipt_image.png"
        img.save(temp_img_path)

        uploaded_file = upload_to_gemini(temp_img_path)
        model = genai.GenerativeModel(model_name="gemini-2.0-flash", generation_config={
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 65536,
            "response_mime_type": "text/plain",
        })

        chat = model.start_chat(history=[{
            "role": "user",
            "parts": [uploaded_file],
        }])

        response = chat.send_message("This is a receipt. What is the total amount paid? Respond only with the number.")
        return response.text.strip()

    except Exception as e:
        return f"Error: {str(e)}"