import requests
import os
import json

# Groq config
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_WHISPER_MODEL = "whisper-large-v3"


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

            If a user refers to an image or total amount and not audio and it's not in the table, DO NOT generate SQL but give the answer in the following format
            if single image then single_image would be true and end_index would be 0 and start index would be the index but do not confuse with audio. Its just for image. Its not for audio. If the user asks for audio then do not give json.

            {
            "task": "process_receipts",
            "start_index": 1,
            "end_index": 10,
            "single_image": False,
            "file_pattern": "refund_req{i}.png",
            }

            Only give that json nothing else if the user asks for images.

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