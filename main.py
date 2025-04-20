import os
import re
import json
import requests
from io import BytesIO
from PIL import Image
from supabase import create_client, Client
from tabulate import tabulate
import google.generativeai as genai

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

# ------------------------ GEMINI IMAGE ANALYSIS ------------------------

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

# ------------------------ GROQ AGENT ------------------------

conversation_history = [
    {
        "role": "system",
        "content": """        
           Convert user input prompts into efficient SQL queries for Supabase that can succeed on the first execution.

            Ensure that the SQL queries account for efficiency, using best practices for query formation specific to Supabase's capabilities.

            # Steps
            1. Understand the User Input
            2. Construct the Query
            3. Validate the Query

            Table: employees  
            Columns:  
            - id (id)  
            - name (text)  
            - age (numeric)
            - salary (numeric)
            - created_at (timestamp with time zone)

            Table: refund_requests
            Columns:
            - id (id)
            - name (text)
            - amount (numeric)
            - image_url (text)
            - audio_url (text)
            - created_at (timestamp with time zone)

            If a user asks to insert or query a column not in this schema, **do not** generate SQL.  
            Instead, explain clearly which columns are allowed and guide the user to correct their request.

            Be strict — do not hallucinate or assume additional columns.
            Only use what's defined in the schema. But little spelling mistakes can be tolerated.

            # Output Format
            Provide a clean, efficient SQL query. The output should be a text response showing only the SQL query.

            Try to include 'image_url' in SQL queries if the user is asking for anything related to a receipt or amount from a scanned image.
        """
    }
]

def get_groq_response(prompt):
    conversation_history.append({"role": "user", "content": prompt})
    payload = {
        "model": GROQ_MODEL,
        "messages": conversation_history,
        "temperature": 0.7
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {GROQ_API_KEY}'
    }
    response = requests.post(GROQ_URL, headers=headers, data=json.dumps(payload))
    result = response.json()
    reply = result['choices'][0]['message']['content']
    conversation_history.append({"role": "assistant", "content": reply})
    return reply

# ------------------------ SUPABASE EXECUTOR ------------------------

def parse_table_name(sql_query):
    match = re.search(r'from\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql_query, re.IGNORECASE)
    if not match:
        match = re.search(r'into\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql_query, re.IGNORECASE)
    return match.group(1) if match else None

def execute_supabase_query(sql_query):
    try:
        if '```sql' in sql_query:
            sql_query = sql_query.split('```sql')[1].split('```')[0].strip()

        query_type = sql_query.strip().split()[0].upper()
        table_name = parse_table_name(sql_query)

        if query_type == "SELECT":
            result = supabase.rpc('run_select_query', {'query_text': sql_query.rstrip(";")}).execute()
            if hasattr(result, 'error') and result.error:
                return {"error": str(result.error)}
            return result.data

        elif query_type in ["INSERT", "UPDATE", "DELETE"]:
            result = supabase.rpc('execute_sql', {'query': sql_query}).execute()
            if hasattr(result, 'error') and result.error:
                return {"error": str(result.error)}
            if table_name:
                data = supabase.table(table_name).select("*").limit(10).execute()
                return {"operation": "success", "fetched_data": data.data}
            else:
                return {"operation": "success"}

        return {"error": f"Unsupported query type: {query_type}"}

    except Exception as e:
        return {"error": str(e)}

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
    # user_input = input("💬 Enter your request: ")
    user_input = "get receipt url with name Robert Jones and amount"

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
            return
        elif isinstance(result, list):
            # Process each receipt image URL
            for item in result:
                if 'image_url' in item:
                    total = extract_total_from_receipt(item['image_url'])
                    print(f"🧾 Total on receipt: Rs. {total}")
                else:
                    print("⚠️ No image URL found in the result.")

    
    

# ------------------------ RUN AGENT ------------------------

if __name__ == "__main__":
    main()
