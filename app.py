import shutil
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import os
import pandas as pd
import sqlite3
import smtplib
from email.message import EmailMessage

from execute_query import execute_query
from generate_sql_query import generate_sql_query

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Required for flash messaging

# Configuration
DATABASE_FILE = "college.db"
USER_TABLE = "users"
DATASET_FOLDER = r"D:\QueryPilot-Project lmm\QueryPilot-Project\final year project\database"

# Helper to get CSV-based database names
def get_available_csv_databases(folder_path):
    return [f.replace(".csv", "") for f in os.listdir(folder_path) if f.endswith(".csv")] if os.path.exists(folder_path) else []

# Initialize SQLite database from CSVs and keep user table
def connectDb(data_folder, db_file):
    global available_dbs
    available_dbs = get_available_csv_databases(data_folder)
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        print("[INIT] Connected to DB")

        # Create 'users' table if it doesn't exist
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {USER_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)
        conn.commit()

        # Populate tables from CSVs
        for db_name in available_dbs:
            csv_path = os.path.join(data_folder, f"{db_name}.csv")
            try:
                df = pd.read_csv(csv_path)
                if df.empty:
                    continue
                df.columns = [col.replace(' ', '_').replace('.', '_').replace('-', '_').lower() for col in df.columns]
                df.to_sql(db_name, conn, if_exists='replace', index=False)
                print(f"[DB] Loaded: {db_name}")
            except Exception as e:
                print(f"[ERROR] Failed to process CSV {db_name}: {e}")
                if db_name in available_dbs:
                    available_dbs.remove(db_name)

        conn.commit()
    except Exception as e:
        print(f"[FATAL] DB Initialization failed: {e}")
    finally:
        if conn:
            conn.close()

# Render Pandas DataFrame as Tailwind styled HTML table
def df_to_tailwind_table(df: pd.DataFrame) -> str:
    if df.empty:
        return '<p class="text-white text-center py-4">No results found.</p>'
    html = '<div class="overflow-x-auto"><table class="min-w-full divide-y divide-gray-700 table-auto">'
    html += '<thead class="bg-gray-700"><tr>'
    html += ''.join(f'<th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">{col}</th>' for col in df.columns)
    html += '</tr></thead><tbody class="bg-gray-800 divide-y divide-gray-700">'
    for _, row in df.iterrows():
        html += '<tr>' + ''.join(f'<td class="px-6 py-4 text-sm text-white whitespace-nowrap">{str(row[col])}</td>' for col in df.columns) + '</tr>'
    html += '</tbody></table></div>'
    return html

# Routes

@app.route('/')
def index():
    return redirect(url_for('signup_page'))

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/signup')
def signup_page():
    return render_template('signup.html')

@app.route('/login', methods=['POST'])
def handle_login():
    username = request.form.get('username')
    password = request.form.get('password')

    if not username or not password:
        flash("Please provide both username and password.")
        return redirect(url_for('login_page'))

    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {USER_TABLE} WHERE username = ? AND password = ?", (username, password))
            result = cursor.fetchone()
            if result:
                flash("Login successful!")
                return redirect(url_for('home_page'))  # changed from 'main_page'
            else:
                flash("Login failed. Incorrect username or password.")
                return redirect(url_for('login_page'))
    except Exception as e:
        flash(f"Login error: {e}")
        return redirect(url_for('login_page'))

@app.route('/signup', methods=['POST'])
def handle_signup():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    confirm = request.form.get('confirm-password')

    if not username or not email or not password or not confirm:
        flash("Please fill out all fields.")
        return redirect(url_for('signup_page'))

    if password != confirm:
        flash("Passwords do not match.")
        return redirect(url_for('signup_page'))

    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(f"INSERT INTO {USER_TABLE} (username, email, password) VALUES (?, ?, ?)", (username, email, password))
            conn.commit()
            flash("Signup successful! Please log in.")
            return redirect(url_for('login_page'))
    except sqlite3.IntegrityError:
        flash("Username or email already exists.")
        return redirect(url_for('signup_page'))
    except Exception as e:
        flash(f"Signup error: {e}")
        return redirect(url_for('signup_page'))

@app.route('/main')
def main_page():
    global available_dbs
    available_dbs = get_available_csv_databases(DATASET_FOLDER)
    return render_template('index.html', databases=available_dbs)

@app.route('/upload-database', methods=['POST'])
def upload_database():
    try:
        if os.path.exists(DATASET_FOLDER):
            shutil.rmtree(DATASET_FOLDER)
        os.makedirs(DATASET_FOLDER)

        files = request.files.getlist('db-upload')
        if not files or all(not file.filename for file in files):
            flash("No files selected for upload.")
            return redirect(url_for('main_page'))

        for file in files:
            if file.filename.endswith('.csv'):
                file.save(os.path.join(DATASET_FOLDER, file.filename))
            else:
                flash(f"Invalid file format for {file.filename}.")
                return redirect(url_for('main_page'))

        connectDb(DATASET_FOLDER, DATABASE_FILE)
        flash("Database uploaded and initialized successfully.")
        return redirect(url_for('main_page'))
    except Exception as e:
        flash(f"Error uploading database: {e}")
        return redirect(url_for('main_page'))

@app.route('/generate_sql', methods=['POST'])
def generate_sql_route():
    data = request.json
    user_query = data.get("user_query")
    db_name = data.get("db_name")

    if not user_query or not db_name:
        return jsonify({"error": "Missing user_query or db_name."}), 400

    try:
        sql_query_result = generate_sql_query(user_query, db_name)

        if any(sql_query_result.upper().startswith(prefix) for prefix in [
            "API REQUEST ERROR:", "API RESPONSE PARSING ERROR:",
            "AN UNEXPECTED ERROR", "GEMINI DID NOT RETURN"
        ]):
            return jsonify({"error": sql_query_result}), 500

        return jsonify({"sql_query": sql_query_result})
    except Exception as e:
        return jsonify({"error": f"Unexpected SQL generation error: {e}"}), 500

@app.route('/execute_query', methods=['POST'])
def execute_sql_route():
    data = request.json
    sql_query = data.get("sql_query")
    if not sql_query:
        return "No SQL query provided", 400

    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            results_df = execute_query(sql_query, conn)
            if "Error" in results_df.columns:
                return f'<p class="text-red-500 text-center py-4">Error: {results_df["Error"].iloc[0]}</p>', 500
            elif "Result" in results_df.columns:
                return f'<p class="text-green-500 text-center py-4">{results_df["Result"].iloc[0]}</p>'
            elif "Status" in results_df.columns:
                return f'<p class="text-green-500 text-center py-4">{results_df["Status"].iloc[0]}</p>'
            else:
                return df_to_tailwind_table(results_df)
    except Exception as e:
        return f'<p class="text-red-500 text-center py-4">Execution Error: {e}</p>', 500

@app.route('/contact', methods=['POST'])
def contact():
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')

    msg = EmailMessage()
    msg['Subject'] = f'QueryPilot Contact from {name}'
    msg['From'] = email
    msg['To'] = 'atheeqzee8@gmail.com'
    msg.set_content(f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}")

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login('atheeqzee8@gmail.com', 'your_gmail_app_password')  # Use an app password if 2FA is enabled
            smtp.send_message(msg)
        flash('Message sent successfully!', 'success')
    except Exception as e:
        flash(f'Failed to send message: {e}', 'danger')
    return redirect(url_for('home_page'))

@app.route('/home')
def home_page():
    return render_template('home.html')

if __name__ == '__main__':
    if not os.path.exists(DATASET_FOLDER):
        os.makedirs(DATASET_FOLDER)
    connectDb(DATASET_FOLDER, DATABASE_FILE)
    app.run(debug=True)
