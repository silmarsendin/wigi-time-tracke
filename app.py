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

# --- APP CONFIG ---
st.set_page_config(page_title="WIGI Time Manager", layout="wide")

# --- LOGIN LOGIC ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("WIGI Time Manager")
    u, p = st.text_input("Username"), st.text_input("Password", type='password')
    if st.button("Access"):
        if c.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p)).fetchone():
            st.session_state['logged_in'], st.session_state['username'] = True, u
            st.rerun()
else:
    # Sidebar styling
    st.markdown("""<style>
        [data-testid="stSidebar"] { background-color: #FFFFFF !important; }
        [data-testid="stSidebar"] * { color: #000000 !important; }
    </style>""", unsafe_allow_html=True)
    
    if os.path.exists("wigi.png"): st.sidebar.image("wigi.png", use_container_width=True)
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()
    
    current_user = st.session_state['username']
    choice = st.sidebar.selectbox("Navigation", ["Project Registration", "Time Tracker", "Reports"])

    # --- RELEVANT SECTION: TIME TRACKER ---
    if choice == "Time Tracker":
        st.header("Work Logging")
        user_data = c.execute("SELECT is_working, start_time_db, active_project_id FROM users WHERE username=?", (current_user,)).fetchone()
        working_now, start_time_str, active_p_id = bool(user_data[0]), user_data[1], user_data[2]

        # Injeção de CSS Dinâmico para cor AZUL
        if working_now:
            st.markdown("""
                <style>
                /* Cor da Palavra (Label) */
                div[data-testid="stToggle"] label p {
                    color: #1E90FF !important;
                    font-weight: bold !important;
                }
                /* Cor do Botão Switch quando TRUE */
                div[data-testid="stToggle"] div[data-testid="stWidgetLabel"] + div div[aria-checked="true"] {
                    background-color: #1E90FF !important;
                }
                </style>
                """, unsafe_allow_html=True)
            
            p_data = c.execute("SELECT name FROM projects WHERE p_number=?", (active_p_id,)).fetchone()
            st.markdown(f'<div style="background-color:#E3F2FD; padding:15px; border-radius:8px; border-left:6px solid #1E90FF; margin-bottom:10px;"><span style="color:#1E90FF; font-weight:bold;">🔵 Status: Working on Project: {p_data[0] if p_data else "Unknown"}</span></div>', unsafe_allow_html=True)
            t_label = "Working"
        else:
            t_label = "Available"

        # Toggle Switch (Informativo)
        st.toggle(t_label, value=working_now, disabled=True)
        
        projs = pd.read_sql("SELECT p_number, name FROM projects WHERE owner=?", conn, params=(current_user,))
        
        if not projs.empty:
            target = st.selectbox("Select Project", [f"{r['p_number']} - {r['name']}" for _, r in projs.iterrows()], key="auto_sel")
            p_id = target.split(" - ")[0]
            c1, c2 = st.columns(2)
            
            if c1.button("▶ START", use_container_width=True, disabled=working_now):
                c.execute("UPDATE users SET is_working=1, start_time_db=?, active_project_id=? WHERE username=?", (datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'), p_id, current_user))
                conn.commit()
                st.rerun()
            
            if c2.button("■ STOP", use_container_width=True, disabled=not working_now):
                if working_now and start_time_str:
                    start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S.%f')
                    diff = (datetime.now() - start_dt).total_seconds() / 3600
                    c.execute("INSERT INTO time_logs VALUES (?,?,?,?,?,?)", (current_user, active_p_id, datetime.now().date(), start_dt, datetime.now(), diff))
                    c.execute("UPDATE projects SET remaining = remaining - ? WHERE p_number = ?", (diff, active_p_id))
                    c.execute("UPDATE users SET is_working=0, start_time_db=NULL, active_project_id=NULL WHERE username=?", (current_user,))
                    conn.commit()
                    st.rerun()
        
        # O restante do código de Manual Adjustment e Reports permanece o mesmo conforme o app.py original
