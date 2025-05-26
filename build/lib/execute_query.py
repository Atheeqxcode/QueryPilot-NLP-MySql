import pandas as pd
import sqlite3

# This DATABASE_FILE variable is not strictly needed here if conn is passed from app.py,
# but it's good practice to keep it consistent if other functions in this file might use it directly.
DATABASE_FILE = "college.db"

def execute_query(query: str, conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Executes an SQL query against the provided SQLite connection and returns
    a Pandas DataFrame. For non-SELECT queries, it returns a DataFrame
    indicating success. For errors, it returns a DataFrame with an error message.

    :param query: The SQL query string to execute.
    :param conn: An active SQLite connection object.
    :return: A Pandas DataFrame containing query results or an error/status message.
    """
    try:
        query = query.strip()

        # Handle SELECT queries
        if query.upper().startswith("SELECT"):
            # Ensure SELECT DISTINCT as you intended for SELECTs, if not already present
            if not query.upper().startswith("SELECT DISTINCT"):
                 query = query.replace("SELECT", "SELECT DISTINCT", 1)
            
            df = pd.read_sql_query(query, conn)
            # If the SELECT query returned no rows, return a DataFrame indicating that
            if df.empty:
                return pd.DataFrame({"Result": ["No records found for your query."]})
            return df

        # Handle other DML/DDL queries (INSERT, UPDATE, DELETE, CREATE, DROP, etc.)
        else:
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            # For non-SELECT queries, return a DataFrame with a success message
            return pd.DataFrame({"Status": ["Query executed successfully."]})

    except sqlite3.Error as e:
        # If a SQLite error occurs during query execution, return a DataFrame with the error message
        return pd.DataFrame({"Error": [f"SQL Error: {e}"]})
    except Exception as e:
        # Catch any other unexpected Python errors and return them in a DataFrame
        return pd.DataFrame({"Error": [f"An unexpected error occurred: {e}"]})