import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
import os

# --- DATABASE SETUP ---
conn = sqlite3.connect('business_manager.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)')
    # Adicionada a coluna 'owner' para isolar os projetos por usuário
    c.execute('''CREATE TABLE IF NOT EXISTS projects 
                 (p_number TEXT PRIMARY KEY, name TEXT, allocated FLOAT, remaining FLOAT, owner TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS time_logs 
                 (user TEXT, project_id TEXT, date DATE, start_time TIMESTAMP, end_time TIMESTAMP, duration FLOAT)''')
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES ('admin', 'admin123')")
    conn.commit()

init_db()

# --- CSS TO FORCE WHITE SIDEBAR ---
st.markdown("""<style>
    [data-testid="stSidebar"] { background-color: #FFFFFF !important; }
    [data-testid="stSidebar"] * { color: #000000 !important; }
</style>""", unsafe_allow_html=True)

# --- PDF FUNCTIONS ---
def generate_project_pdf(project_name, remaining):
    file_path = f"report_{project_name}.pdf"
    pdf = canvas.Canvas(file_path, pagesize=A4)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, 800, f"Project Status Report: {project_name}")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 770, f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    pdf.drawString(50, 750, f"Current Balance: {remaining:.2f} hours")
    pdf.save()
    return file_path

def generate_weekly_pdf(df, start_date):
    file_path = "weekly_summary.pdf"
    pdf = canvas.Canvas(file_path, pagesize=landscape(A4))
    data = [["Project"] + [col.strftime('%a %d/%m') for col in df.columns]]
    for index, row in df.iterrows():
        data.append([index] + [f"{v:.2f}" for v in row.values])
    table = Table(data)
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    table.wrapOn(pdf, 50, 400); table.drawOn(pdf, 50, 400); pdf.save()
    return file_path

# --- APP INTERFACE ---
st.set_page_config(page_title="WIGI Time Manager", layout="wide")

if os.path.exists("wigi.png"):
    st.sidebar.image("wigi.png", use_container_width=True)

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("WIGI Time Manager")
    t1, t2 = st.tabs(["Login", "Register"])
    with t1:
        u = st.text_input("Username")
        p = st.text_input("Password", type='password')
        if st.button("Access"):
            if c.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p)).fetchone():
                st.session_state['logged_in'], st.session_state['username'] = True, u
                st.rerun()
            else: st.error("Wrong credentials")
    with t2:
        nu = st.text_input("New Username")
        np = st.text_input("New Password", type='password')
        if st.button("Create Account"):
            try:
                c.execute("INSERT INTO users VALUES (?,?)", (nu, np)); conn.commit()
                st.success("User created!")
            except: st.error("User already exists")

else:
    st.sidebar.markdown(f"### User: **{st.session_state['username']}**")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()
    
    current_user = st.session_state['username']
    choice = st.sidebar.selectbox("Navigation", ["Project Registration", "Time Tracker", "Weekly Reports"])

    if choice == "Project Registration":
        st.header("My Projects")
        with st.form("p_reg"):
            col1, col2 = st.columns(2)
            num, name = col1.text_input("Project ID"), col2.text_input("Project Name")
            hours = st.number_input("Allocated Time", min_value=0.0)
            if st.form_submit_button("Save Project"):
                try:
                    # Agora salvamos o 'current_user' como dono (owner)
                    c.execute("INSERT INTO projects VALUES (?,?,?,?,?)", (num, name, hours, hours, current_user))
                    conn.commit(); st.success("Project Registered!"); st.rerun()
                except: st.error("Project ID already exists.")
        
        # Filtrar tabela para mostrar apenas projetos do usuário logado
        my_projs = pd.read_sql("SELECT p_number, name, allocated, remaining FROM projects WHERE owner=?", conn, params=(current_user,))
        st.dataframe(my_projs, use_container_width=True)

    elif choice == "Time Tracker":
        st.header("Work Logging")
        # Apenas projetos do usuário logado no dropdown
        projs = pd.read_sql("SELECT p_number, name FROM projects WHERE owner=?", conn, params=(current_user,))
        if not projs.empty:
            target = st.selectbox("Select Project", [f"{r['p_number']} - {r['name']}" for _, r in projs.iterrows()])
            p_id = target.split(" - ")[0]
            c1, c2 = st.columns(2)
            if c1.button("▶ START"):
                st.session_state['start_time'] = datetime.now()
            if c2.button("■ STOP"):
                if 'start_time' in st.session_state:
                    diff = (datetime.now() - st.session_state['start_time']).total_seconds() / 3600
                    c.execute("INSERT INTO time_logs VALUES (?,?,?,?,?,?)", (current_user, p_id, datetime.now().date(), st.session_state['start_time'], datetime.now(), diff))
                    c.execute("UPDATE projects SET remaining = remaining - ? WHERE p_number = ? AND owner = ?", (diff, p_id, current_user))
                    conn.commit()
                    data = c.execute("SELECT remaining, allocated FROM projects WHERE p_number = ?", (p_id,)).fetchone()
                    st.success(f"Logged {diff:.2f}h. Balance: {data[0]:.2f}h ({ (data[0]/data[1]*100):.1f}%)")
                    del st.session_state['start_time']

    elif choice == "Weekly Reports":
        st.header("Your Weekly Summary")
        today = datetime.now().date()
        last_monday = today - timedelta(days=today.weekday())
        week_days = [last_monday + timedelta(days=i) for i in range(7)]
        
        # Filtro de logs pelo usuário logado
        logs = pd.read_sql("SELECT project_id, date, duration FROM time_logs WHERE date >= ? AND user = ?", conn, params=(last_monday, current_user))
        my_p_list = pd.read_sql("SELECT p_number FROM projects WHERE owner=?", conn, params=(current_user,))['p_number'].tolist()
        
        weekly_df = pd.DataFrame(index=my_p_list, columns=week_days).fillna(0.0)
        for _, row in logs.iterrows():
            log_date = datetime.strptime(str(row['date']), '%Y-%m-%d').date() if isinstance(row['date'], str) else row['date']
            if log_date in weekly_df.columns and row['project_id'] in weekly_df.index:
                weekly_df.at[row['project_id'], log_date] += row['duration']
        
        display_df = weekly_df.copy()
        display_df.columns = [d.strftime('%a (%d/%m)') for d in weekly_df.columns]
        st.dataframe(display_df, use_container_width=True)
        
        if st.button("Export Weekly PDF"):
            w_path = generate_weekly_pdf(weekly_df, last_monday)
            with open(w_path, "rb") as f: st.download_button("Download PDF", f, file_name=w_path)
