import os
import pandas as pd
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not found in .env. Please check your .env file.")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"


def generate_sql_query(user_query: str, db_name: str) -> str:
    """
    Generates an SQL query based on user natural language query and selected database schema
    using the Gemini API. Returns the generated SQL query string or a detailed error message string.

    :param user_query: The natural language query from the user.
    :param db_name: The name of the selected database table (corresponding to a CSV file).
    :return: The generated SQL query string or an error message string.
    """
    # !!! IMPORTANT: VERIFY THIS PATH ON YOUR SYSTEM !!!
    # This should point to the folder containing your CSV database files.
    DATASET_FOLDER = r"D:\QueryPilot-Project lmm\QueryPilot-Project\final year project\database"

    # List all CSV files in the database folder to build schema context for the AI
    csv_file_paths = [os.path.join(DATASET_FOLDER, f)
                      for f in os.listdir(DATASET_FOLDER)
                      if f.endswith('.csv')]
    
    table_definitions = ""
    table_counter = 1 # Used for numbering tables in the prompt for clarity

    for path in csv_file_paths:
        table_name = os.path.splitext(os.path.basename(path))[0]
        try:
            # Read only headers (first 0 rows) for efficiency to get column names
            df = pd.read_csv(path, nrows=0)
            # Sanitize column names for prompt to match SQLite loading and avoid issues
            columns = [col.replace(' ', '_').replace('.', '_').replace('-', '_').lower() for col in df.columns.tolist()]
            
            table_definitions += f"\n\n{table_counter}. `{table_name}`:\n"
            for col in columns:
                table_definitions += f"- `{col}` (text)\n" # Assume all columns are text for SQL generation
            table_counter += 1
        except Exception as e:
            # Include an error in the schema definition if a CSV can't be read
            table_definitions += f"\n\n# Error reading schema for {table_name}: {e}\n"

    # The prompt sent to the Gemini API
    prompt = f"""
        You are an expert in converting English questions to SQL code! The SQL database has these tables:{table_definitions}

        Convert the following natural language query to a **valid SQL query** for a CSV-based database.

        - The table name is `{db_name}`.
        - Do not return JSON or any explanation.
        - Return **only** the SQL query.
        - Use correct column names from the database, matching the sanitized names (e.g., 'department_name' not 'Department Name').
        - Do not include ```sql or ```json formatting.
        - If user query contains part of column_name, include it in sql query.

        Example 1: What is the name of the student with ID 1?
        SQL: SELECT name FROM Students WHERE student_id = 1;

        Example 2: How many students are enrolled in the Computer Science department?
        SQL: SELECT COUNT(*) FROM Students WHERE department = 'Computer Science';

        Example 3: List all courses taught by Dr. Smith.
        SQL: SELECT c.course_name FROM Courses c JOIN Teachers t ON c.department_id = t.department_id WHERE t.name = 'Dr. Smith';

        Example 4: Find the total number of books in the library.
        SQL: SELECT COUNT(*) FROM Books;

        Example 5: Show the attendance status of student ID 2 for course ID 101.
        SQL: SELECT status FROM Attendance WHERE student_id = 2 AND course_id = 101;

        User: Show all names of students with GPA above 3.5.
        SQL: SELECT student_name FROM students WHERE gpa > 3.5;

        User: Show all students with GPA above 3.5.
        SQL: SELECT * FROM students WHERE gpa > 3.5;

        Now, convert this query:

        User: {user_query}
        SQL:
    """

    headers = {
        "Content-Type": "application/json"
    }

    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        # Make the POST request to Gemini API
        response = requests.post(GEMINI_API_URL, headers=headers, json=data)
        
        # Raise an exception for HTTP errors (4xx or 5xx status codes)
        response.raise_for_status() 
        result = response.json()
        
        # Safely extract the generated text from the JSON response
        content = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        
        # Clean the generated SQL (remove markdown code blocks and excess whitespace)
        sql_query = content.replace("```sql", "").replace("```", "").strip()
        
        # Basic validation: check if it resembles a SQL query
        if any(sql_query.upper().startswith(keyword) for keyword in ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"]):
            return sql_query
        else:
            # If the generated content doesn't look like SQL, return an error message
            return f"Gemini did not return a valid SQL query. Unexpected response: {content}"
    
    except requests.exceptions.RequestException as e:
        # Catch network-related errors (e.g., connection issues, DNS errors, HTTP errors)
        return f"API Request Error: {e}"
    except (KeyError, IndexError, TypeError) as e:
        # Catch errors if the API response JSON structure is unexpected
        return f"API Response Parsing Error: {e}. Full response: {json.dumps(result, indent=2)}"
    except Exception as e:
        # Catch any other unforeseen errors during the process
        return f"An unexpected error occurred during SQL generation: {e}"