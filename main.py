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

# ------------------------ CONFIGURATION ------------------------

# Supabase config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Gemini config
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Groq config
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_WHISPER_MODEL = "whisper-large-v3"


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
        

        # Check if the query requires image_url (receipt)
        if "image_url" in sql_query and any(word in user_input.lower() for word in ["amount", "total"]):
            print("📷 Detected visual query. Using Gemini to scan receipt...")
            # check type of result is dict
            if isinstance(result, dict):
                # Process receipt with Gemini
                total = extract_total_from_receipt(result['image_url'])
                print(f"🧾 Total on receipt: Rs. {total}")
                if total:
                    # update the supabase table with that amount with by comparing image_url to get teh row
                    res = supabase.table("refund_requests").update({"amount": total}).eq("image_url", result['image_url']).execute() 
                    if not res:
                        print("⚠️ Failed to update the amount in the database.")
            elif isinstance(result, list):
                # Process each receipt image URL
                for item in result:
                    if 'image_url' in item:
                        total = extract_total_from_receipt(item['image_url'])
                        print(f"🧾 Total on receipt: Rs. {total}")
                        res = supabase.table("refund_requests").update({"amount": total}).eq("image_url", result['image_url']).execute() 
                        if not res:
                            print("⚠️ Failed to update the amount in the database.")
                    else:
                        print("⚠️ No image URL found in the result.")

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
