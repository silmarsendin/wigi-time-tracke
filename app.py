import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
import os

# =========================================================
# PATH SETUP (PERSISTENT & SAFE)
# =========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "business_manager.db")

# =========================================================
# DATABASE CONNECTION
# =========================================================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            is_working INTEGER DEFAULT 0,
            start_time_db TEXT,
            active_project_id TEXT,
            manager INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            p_number TEXT PRIMARY KEY,
            name TEXT,
            allocated REAL,
            remaining REAL,
            owner TEXT,
            finished INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS time_logs (
            user TEXT,
            project_id TEXT,
            date DATE,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration REAL
        )
    """)

    c.execute("""
        INSERT OR IGNORE INTO users (username, password, manager)
        VALUES ('admin', 'admin123', 1)
    """)

    conn.commit()

# Run DB init only once per session
if "db_initialized" not in st.session_state:
    init_db()
    st.session_state["db_initialized"] = True

# =========================================================
# STREAMLIT CONFIG
# =========================================================
st.set_page_config(page_title="WIGI Ti_
