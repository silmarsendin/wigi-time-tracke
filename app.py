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

# --- DATABASE SETUP ---
conn = sqlite3.connect('business_manager.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, is_working INTEGER DEFAULT 0, 
                  start_time_db TEXT, active_project_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS projects 
                 (p_number TEXT PRIMARY KEY, name TEXT, allocated FLOAT, remaining FLOAT, owner TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS time_logs 
                 (user TEXT, project_id TEXT, date DATE, start_time TIMESTAMP, end_time TIMESTAMP, duration FLOAT)''')
    
    cols = [column[1] for column in c.execute("PRAGMA table_info(users)")]
    if "is_working" not in cols: c.execute("ALTER TABLE users ADD COLUMN is_working INTEGER DEFAULT 0")
    if "start_time_db" not in cols: c.execute("ALTER TABLE users ADD COLUMN start_time_db TEXT")
    if "active_project_id" not in cols: c.execute("ALTER TABLE users ADD COLUMN active_project_id TEXT")
    
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES ('admin', 'admin123')")
    conn.commit()

init_db()

# --- CSS INTERFACE ---
st.set_page_config(page_title="WIGI Time Manager", layout="wide")
st.markdown("""<style>
    [data-testid="stSidebar"] { background-color: #FFFFFF !important; }
    [data-testid="stSidebar"] * { color: #000000 !important; }
</style>""", unsafe_allow_html=True)

# --- FUNÇÕES DE PDF (CORREÇÃO DO LOGO) ---

def generate_detailed_project_pdf(project_id, project_name, logs_df, remaining):
    file_path = f"detailed_report_{project_id}.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=A4, topMargin=1*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elements = []
    
    if os.path.exists("wigi.png"):
        try:
