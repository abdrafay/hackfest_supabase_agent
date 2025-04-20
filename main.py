import os
import re
import json
import requests
from io import BytesIO
from PIL import Image
from supabase import create_client, Client
from tabulate import tabulate
import google.generativeai as genai

from gemini_vision import extract_total_from_receipt
from audio_transcriber import transcribe_audio_from_url
from supabase_helper import execute_supabase_query
from groq_agent import get_groq_response
import json_repair

# ------------------------ CONFIGURATION ------------------------

# Supabase config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = 'receipt-images'

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Gemini config
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Groq config
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_WHISPER_MODEL = "whisper-large-v3"


# ------------------------ UTILITIES ------------------------

def fetch_image_url_from_storage(file_name):
    return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{file_name}"

def process_receipt_batch(task_info):
    start = task_info["start_index"]
    end = task_info["end_index"]
    file_pattern = task_info["file_pattern"]
    table = "refund_requests"
    image_url_col = "image_url"
    amount_col = "amount"
    id_col = "id"

    for i in range(start, end + 1):
        file_name = file_pattern.replace("{i}", str(i))
        image_url = fetch_image_url_from_storage(file_name)

        print(f"\n📄 Processing {file_name} (row id = {i})")
        total = extract_total_from_receipt(image_url)
        print(f"🧾 Extracted Total: {total}")

        if total and total.replace('.', '', 1).isdigit():
            update_result = supabase.table(table).update({
                image_url_col: image_url,
                amount_col: float(total)
            }).eq(id_col, i).execute()

            if update_result.data:
                print(f"✅ Updated row {i}")
            else:
                print(f"⚠️ Failed to update row {i}")
        else:
            print(f"❌ Could not extract valid total from image {file_name}")

def process_receipt_single(task_info):
    file_name = task_info["file_name"]
    image_url = fetch_image_url_from_storage(file_name)
    print(f"\n📄 Processing {file_name}")
    total = extract_total_from_receipt(image_url)
    print(f"🧾 Extracted Total: {total}")

    if total and total.replace('.', '', 1).isdigit():
        update_result = supabase.table("refund_requests").update({
            "image_url": image_url,
            "amount": float(total)
        }).eq("id", task_info['start_index']).execute()

        if update_result.data:
            print(f"✅ Updated row {task_info['row_id']}")
        else:
            print(f"⚠️ Failed to update row {task_info['row_id']}")
    else:
        print(f"❌ Could not extract valid total from image {file_name}")



# ------------------------ OUTPUT FORMATTER ------------------------

def format_llm_response(user_prompt, sql_query, result):
    system_msg = {
        "role": "system",
        "content": """
            You are a helpful assistant that explains SQL result in plain English.
            If SELECT: show a table.
            If INSERT/DELETE: give summary.
            If error: explain simply.
        """
    }
    user_msg = {
        "role": "user",
        "content": f"""Original user request: {user_prompt}

Generated SQL: {sql_query}

Supabase Result: {json.dumps(result, indent=2)}
"""
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [system_msg, user_msg],
        "temperature": 0.7
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {GROQ_API_KEY}'
    }
    response = requests.post(GROQ_URL, headers=headers, data=json.dumps(payload))
    return response.json()['choices'][0]['message']['content']

def dicts_to_table(data):
    if isinstance(data, list) and all(isinstance(d, dict) for d in data):
        return tabulate(data, headers="keys", tablefmt="grid")
    return "Data is not in expected format."

def render_result(user_prompt, sql_query, result):
    if isinstance(result, dict) and "error" in result:
        print(format_llm_response(user_prompt, sql_query, result))
    elif isinstance(result, list):
        print(dicts_to_table(result))
    elif isinstance(result, dict) and "fetched_data" in result:
        print(format_llm_response(user_prompt, sql_query, result))
    else:
        print("Unknown result format or no data returned.")

# ------------------------ MASTER AGENT LOGIC ------------------------

def main():
    while True:
        # user_input = input("💬 Enter your request: ")
        user_input = input("💬 Enter your request (or 'exit' to quit): ")
        
        if user_input.lower() == 'exit':
            break

        # Get natural language → SQL from Groq
        sql_query = get_groq_response(user_input)


        print("💡 Generated SQL:\n", sql_query)

        # Run regular SQL query otherwise
        result = execute_supabase_query(sql_query)
        render_result(user_input, sql_query, result)
        

        if "process_receipts" in sql_query:
            # regex to get json from the sql_query ```json
            json_str = re.search(r'```json\s*(\{.*?\})\s*```|(\{.*\})', sql_query, re.DOTALL)
            if json_str:
                extracted_json = json_str.group(1) if json_str.group(1) else json_str.group(2)
        
                task = json_repair.loads(extracted_json)
                if task['single_image']:
                    print("⚠️ Single image detected. Processing...")
                    # Process single image
                    process_receipt_single(task)
                else:
                    print("⚠️ Batch processing detected. Processing...")
                    # Process batch of images
                    process_receipt_batch(task)
            return

        if "audio_url" in sql_query:
            print("🎙️ Detected audio transcription request using Whisper...")

            if isinstance(result, dict) and 'audio_url' in result:
                transcription = transcribe_audio_from_url(result['audio_url'])
                print(f"📝 Summarized Transcription: {transcription}")
            elif isinstance(result, list):
                for item in result:
                    if 'audio_url' in item:
                        transcription = transcribe_audio_from_url(item['audio_url'])
                        print(f"📝 Summarized Transcription: {transcription}")
                    else:
                        print("⚠️ No audio URL found in result.")
    

# ------------------------ RUN AGENT ------------------------

if __name__ == "__main__":
    main()
