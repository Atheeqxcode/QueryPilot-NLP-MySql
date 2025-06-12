import os
import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine
from dotenv import load_dotenv
import sqlite3

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

print(f"Loaded DB_URL: {os.getenv('DB_URL')}")
print(f"All env: {dict(os.environ)}")

AIVEN_DB_URL = os.getenv('DB_URL')
DATABASE_FOLDER = os.path.join(os.path.dirname(__file__), 'database')

if not AIVEN_DB_URL:
    raise RuntimeError("DB_URL not found in .env. Please set your Aiven connection string.")

engine = create_engine(AIVEN_DB_URL)

# List all CSV files in the database folder
def get_csv_files(folder):
    return [f for f in os.listdir(folder) if f.endswith('.csv')]

# Migrate each CSV to the cloud DB
def migrate_all_csvs():
    csv_files = get_csv_files(DATABASE_FOLDER)
    for csv_file in csv_files:
        table_name = os.path.splitext(csv_file)[0].replace('-', '_').replace(' ', '_').replace('.', '_').lower()
        csv_path = os.path.join(DATABASE_FOLDER, csv_file)
        print(f"Migrating {csv_file} to table {table_name} ...")
        try:
            df = pd.read_csv(csv_path)
            df.columns = [col.replace(' ', '_').replace('.', '_').replace('-', '_').lower() for col in df.columns]
            # Add an auto-increment id column if not present
            if 'id' not in df.columns:
                df.insert(0, 'id', range(1, 1 + len(df)))
            from sqlalchemy import Table, MetaData, Column, Integer, BigInteger, Text
            metadata = MetaData()
            columns = [Column('id', Integer, primary_key=True, autoincrement=True)]
            for col in df.columns:
                if col == 'id':
                    continue
                # Use BigInteger for '#' column, Text for others
                if col == '#':
                    columns.append(Column(col, BigInteger))
                else:
                    columns.append(Column(col, Text))
            table = Table(table_name, metadata, *columns)
            metadata.drop_all(engine, [table], checkfirst=True)  # Drop if exists to avoid duplicate PK error
            metadata.create_all(engine, tables=[table], checkfirst=True)
            df.to_sql(table_name, engine, if_exists='append', index=False, method=None)
            print(f"[SUCCESS] Migrated {csv_file} to {table_name}")
        except Exception as e:
            print(f"[ERROR] Failed to migrate {csv_file}: {e}")

def migrate_sqlite_db(sqlite_path, engine):
    print(f"Migrating all tables from {sqlite_path} to Aiven cloud DB...")
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    for table in tables:
        print(f"Migrating table: {table}")
        # Quote table name for SQLite if it contains special characters
        safe_table = table
        if not table.isidentifier() or "-" in table or " " in table:
            safe_table = f'"{table}"'
        df = pd.read_sql_query(f"SELECT * FROM {safe_table}", conn)
        # Sanitize columns
        df.columns = [col.replace(' ', '_').replace('.', '_').replace('-', '_').lower() for col in df.columns]
        # Add id column if not present
        if 'id' not in df.columns:
            df.insert(0, 'id', range(1, 1 + len(df)))
        from sqlalchemy import Table, MetaData, Column, Integer, BigInteger, Text
        metadata = MetaData()
        columns = [Column('id', Integer, primary_key=True, autoincrement=True)]
        for col in df.columns:
            if col == 'id':
                continue
            columns.append(Column(col, Text))
        table_obj = Table(table, metadata, *columns)
        metadata.drop_all(engine, [table_obj], checkfirst=True)
        metadata.create_all(engine, tables=[table_obj], checkfirst=True)
        df.to_sql(table, engine, if_exists='append', index=False, method=None)
        print(f"[SUCCESS] Migrated table: {table}")
    conn.close()

if __name__ == "__main__":
    migrate_all_csvs()
    migrate_sqlite_db(os.path.join(os.path.dirname(__file__), 'college.db'), engine)
    print("All CSVs and SQLite tables migrated to Aiven cloud database.")
