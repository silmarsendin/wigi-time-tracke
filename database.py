import sqlite3
import pandas as pd
import os

DB_PATH = os.path.join("data", "business_manager.db")

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY, password TEXT, is_working INTEGER DEFAULT 0,
                start_time_db TEXT, active_project_id TEXT, manager INTEGER DEFAULT 0)""")
    # ... (restante das tabelas como no seu código original)
    c.execute("INSERT OR IGNORE INTO users (username, password, manager) VALUES ('admin','admin123',1)")
    conn.commit()
    conn.close()

def run_query(query, params=(), fetchone=False, is_pandas=False):
    conn = get_connection()
    if is_pandas:
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        return df
    
    c = conn.cursor()
    c.execute(query, params)
    result = c.fetchone() if fetchone else c.fetchall()
    conn.commit()
    conn.close()
    return result
