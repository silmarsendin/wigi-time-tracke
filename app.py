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
    # Adicionadas colunas para persistir o tempo e o projeto entre sessões
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, is_working INTEGER DEFAULT 0, 
                  start_time_db TEXT, active_project_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS projects 
                 (p_number TEXT PRIMARY KEY, name TEXT, allocated FLOAT, remaining FLOAT, owner TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS time_logs 
                 (user TEXT, project_id TEXT, date DATE, start_time TIMESTAMP, end_time TIMESTAMP, duration FLOAT)''')
    
    # Migração para garantir que as novas colunas existam
    cols = [column[1] for column in c.execute("PRAGMA table_info(users)")]
    if "is_working" not in cols: c.execute("ALTER TABLE users ADD COLUMN is_working INTEGER DEFAULT 0")
    if "start_time_db" not in cols: c.execute("ALTER TABLE users ADD COLUMN start_time_db TEXT")
    if "active_project_id" not in cols: c.execute("ALTER TABLE users ADD COLUMN active_project_id TEXT")
    
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES ('admin', 'admin123')")
    conn.commit()

init_db()

# --- FUNÇÕES DE PDF (Mantidas Verticais) ---
# [As funções generate_detailed_project_pdf e generate_weekly_pdf permanecem iguais]

# --- APP INTERFACE ---
st.set_page_config(page_title="WIGI Time Manager", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("WIGI Time Manager")
    u = st.text_input("Username")
    p = st.text_input("Password", type='password')
    if st.button("Access"):
        if c.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p)).fetchone():
            st.session_state['logged_in'], st.session_state['username'] = True, u
            st.rerun()
else:
    current_user = st.session_state['username']
    choice = st.sidebar.selectbox("Navigation", ["Project Registration", "Time Tracker", "Weekly Reports"])

    if choice == "Time Tracker":
        st.header("Work Logging")
        
        # BUSCAR DADOS PERSISTIDOS DO BANCO
        user_data = c.execute("SELECT is_working, start_time_db, active_project_id FROM users WHERE username=?", (current_user,)).fetchone()
        working_now = bool(user_data[0]) if user_data else False
        start_time_str = user_data[1] if user_data else None
        active_p_id = user_data[2] if user_data else None

        if working_now and active_p_id:
            p_name = c.execute("SELECT name FROM projects WHERE p_number=?", (active_p_id,)).fetchone()
            active_project_name = p_name[0] if p_name else "Unknown"
            
            st.markdown("""<style>
                div[data-testid="stToggle"] > label { color: #1E90FF !important; font-weight: bold; }
                .working-box { background-color: #E3F2FD; padding: 15px; border-radius: 8px; border-left: 6px solid #1E90FF; margin-bottom: 20px; color: #1E90FF; }
            </style>""", unsafe_allow_html=True)
            st.markdown(f'<div class="working-box">🔵 <b>Status:</b> Working on Project: <b>{active_project_name}</b></div>', unsafe_allow_html=True)
        
        st.toggle("Working", value=working_now, disabled=True)

        projs = pd.read_sql("SELECT p_number, name FROM projects WHERE owner=?", conn, params=(current_user,))
        
        st.subheader("Automatic Tracker")
        if not projs.empty:
            target = st.selectbox("Select Project", [f"{r['p_number']} - {r['name']}" for _, r in projs.iterrows()], key="auto_sel")
            p_id = target.split(" - ")[0]
            
            c1, c2 = st.columns(2)
            if c1.button("▶ START", use_container_width=True):
                now = datetime.now()
                # Salva o estado e a hora de início no banco de dados para persistência total
                c.execute("UPDATE users SET is_working=1, start_time_db=?, active_project_id=? WHERE username=?", 
                          (now.strftime('%Y-%m-%d %H:%M:%S.%f'), p_id, current_user))
                conn.commit()
                st.rerun()

            if c2.button("■ STOP", use_container_width=True):
                if working_now and start_time_str:
                    start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S.%f')
                    diff = (datetime.now() - start_dt).total_seconds() / 3600
                    
                    # Salva o log e limpa os campos de controle no banco
                    c.execute("INSERT INTO time_logs VALUES (?,?,?,?,?,?)", (current_user, active_p_id, datetime.now().date(), start_dt, datetime.now(), diff))
                    c.execute("UPDATE projects SET remaining = remaining - ? WHERE p_number = ?", (diff, active_p_id))
                    c.execute("UPDATE users SET is_working=0, start_time_db=NULL, active_project_id=NULL WHERE username=?", (current_user,))
                    conn.commit()
                    st.success(f"Logged {diff:.2f}h!")
                    st.rerun()

        st.divider()
        st.subheader("Manual Time Adjustment")
        with st.form("manual_adjust"):
            sel_manual = st.selectbox("Select Project", [f"{r['p_number']} - {r['name']}" for _, r in projs.iterrows()], key="man_sel")
            man_hours = st.number_input("Hours to Adjust", min_value=0.1, step=0.1)
            man_action = st.radio("Action", ["Add Work Time (Reduces Balance)", "Remove Work Time (Increases Balance)"], horizontal=True)
            if st.form_submit_button("Apply Adjustment"):
                p_id_man = sel_manual.split(" - ")[0]
                val = man_hours if "Add" in man_action else -man_hours
                c.execute("UPDATE projects SET remaining = remaining - ? WHERE p_number = ?", (val, p_id_man))
                c.execute("INSERT INTO time_logs VALUES (?,?,?,?,?,?)", (current_user, p_id_man, datetime.now().date(), "MANUAL", "MANUAL", val))
                conn.commit(); st.success("Adjusted!"); st.rerun()

    # ... [Restante do código de Registro e Relatórios permanece igual]
