import re
from supabase import create_client, Client
import os

# Supabase config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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