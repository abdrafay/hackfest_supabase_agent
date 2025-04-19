import requests
import json
import re
from supabase import create_client, Client
from tabulate import tabulate
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize conversation history with the system message
conversation_history = [
    {
        "role": "system",
        "content": """        
            Convert user input prompts into efficient SQL queries for Supabase that can succeed on the first execution.

            Ensure that the SQL queries account for efficiency, using best practices for query formation specific to Supabase's capabilities.

            # Steps
            1. **Understand the User Input**: Break down the user's request to determine the tables involved, desired data filters, and any specific conditions or sorting required.
            2. **Construct the Query**: Develop the SQL query while considering indexing, table joins, filtering, sorting, and data retrieval optimizations.
            3. **Validate the Query**: Ensure the query is syntactically correct and efficient, adhering to Supabase's SQL standards and features.

            # Output Format
            Provide a clean, efficient SQL query. The output should be a text response showing only the SQL query."""
    }
]

def get_groq_response(prompt):
    global conversation_history
    
    # Add user message to history
    conversation_history.append({
        "role": "user",
        "content": prompt
    })
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": conversation_history,
        "temperature": 0.7
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {GROQ_API_KEY}'
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    response_data = response.json()
    
    # Get assistant's reply
    assistant_reply = response_data['choices'][0]['message']['content']
    
    # Add assistant's reply to history
    conversation_history.append({
        "role": "assistant",
        "content": assistant_reply
    })
    
    return assistant_reply


def parse_table_name(sql_query):
    """Extract the table name from a SQL query."""
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
            # Remove any semicolons
            sql_query = sql_query.rstrip(";")
            result = supabase.rpc('run_select_query', {'query_text': sql_query}).execute()
            if hasattr(result, 'error') and result.error:
                return {"error": str(result.error)}
            return result.data

        elif query_type in ["INSERT", "UPDATE", "DELETE"]:
            # Execute the modification
            result = supabase.rpc('execute_sql', {'query': sql_query}).execute()
            if hasattr(result, 'error') and result.error:
                return {"error": str(result.error)}

            # Fetch updated data from table
            if table_name:
                table_result = supabase.table(table_name).select("*").limit(10).execute()
                return {
                    "operation": "success",
                    "fetched_data": table_result.data
                }
            else:
                return {"operation": "success", "note": "Could not detect table name for data fetch."}

        else:
            return {"error": f"Unsupported query type: {query_type}"}

    except Exception as e:
        return {"error": str(e)}
    
def format_llm_response(user_prompt, sql_query, supabase_result):
    """Send the result to a second LLM for pretty formatting or explanation."""
    system_msg = {
        "role": "system",
        "content": """
        You are a helpful assistant that receives SQL execution results and presents them in a clear, user-friendly format.

        Your tasks:
        1. If data is returned (e.g., from a SELECT), present it as a neat, readable table.
        2. If an INSERT/UPDATE/DELETE operation succeeded, confirm it with a helpful summary.
        3. If there's an error, explain what went wrong in simple terms.

        Avoid showing raw JSON. Be concise, human-friendly, and clear.
        """
    }

    user_msg = {
        "role": "user",
        "content": f"""Original user request: {user_prompt}

Generated SQL: {sql_query}

Supabase Result: {json.dumps(supabase_result, indent=2)}
"""
    }

    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [system_msg, user_msg],
        "temperature": 0.7
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {GROQ_API_KEY}'
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    response_data = response.json()
    return response_data['choices'][0]['message']['content']


def dicts_to_table(data):
    if isinstance(data, list) and all(isinstance(d, dict) for d in data):
        return tabulate(data, headers="keys", tablefmt="grid")
    return "Data is not in expected format for tabulation."

# Example usage:
if __name__ == "__main__":
    # First get the SQL query from Groq

    # while True:
        # user_input = input("Please enter your SQL request: ")
        # if user_input.lower() == 'exit':
        #     break
        # sql_query = get_groq_response(user_input)
        # print("Generated SQL:", sql_query)
        
        # # Execute the generated SQL query
        # result = execute_supabase_query(sql_query)
        # print("Supabase Result:", result)
    user_input = "get all employees"
    sql_query1 = get_groq_response(user_input)
    print("Generated SQL:", sql_query1)
    
    # Then execute it with Supabase
    result1 = execute_supabase_query(sql_query1)
    print("Supabase Result:", result1)
    print(dicts_to_table(result1))
    # pretty_response = format_llm_response(user_input, sql_query1, result1)
    # print("Formatted LLM Response:\n", pretty_response)

    # sql_query1 = get_groq_response("insert a row in employees with the name John Hasnain, salary 40000")
    # print("Generated SQL:", sql_query1)
    
    # # Then execute it with Supabase
    # result1 = execute_supabase_query(sql_query1)
    # print("Supabase Result:", result1)
    
    # Second query with context
    # sql_query2 = get_groq_response("update the new row 5535e2f0-3cfb-4cc4-8d95-474ca672208b, make John's age 200")
    # print("Generated SQL:", sql_query2)
    
    # # Execute the second query
    # result2 = execute_supabase_query(sql_query2)
    # print("Supabase Result:", result2)