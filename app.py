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
    c.execute('''CREATE TABLE IF NOT EXISTS projects 
                 (p_number TEXT PRIMARY KEY, name TEXT, allocated FLOAT, remaining FLOAT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS time_logs 
                 (user TEXT, project_id TEXT, date DATE, start_time TIMESTAMP, end_time TIMESTAMP, duration FLOAT)''')
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES ('admin', 'admin123')")
    conn.commit()

init_db()

# --- CSS TO FORCE WHITE SIDEBAR ---
st.markdown("""<style>
    [data-testid="stSidebar"] { background-color: #FFFFFF !important; }
    [data-testid="stSidebar"] * { color: #000000 !important; }
    [data-testid="stSidebar"] .stSelectbox div { color: #000000 !important; }
</style>""", unsafe_allow_html=True)

# --- PDF GENERATION FUNCTIONS ---
def generate_project_pdf(project_name, remaining):
    file_path = f"report_{project_name}.pdf"
    pdf = canvas.Canvas(file_path, pagesize=A4)
    pdf.setTitle(f"Project Report - {project_name}")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, 800, f"Project Status Report: {project_name}")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 770, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    pdf.drawString(50, 750, f"Current Balance: {remaining:.2f} hours")
    pdf.save()
    return file_path

def generate_weekly_pdf(df, start_date):
    file_path = "weekly_summary.pdf"
    pdf = canvas.Canvas(file_path, pagesize=landscape(A4))
    pdf.setTitle("Weekly Report")
    
    # Title
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, 550, f"Weekly Timesheet - Starting Monday: {start_date}")
    
    # Convert DataFrame to List for Table
    data = [["Project"] + [col.strftime('%a %d/%m') for col in df.columns]]
    for index, row in df.iterrows():
        data.append([index] + [f"{v:.2f}" for v in row.values])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    
    table.wrapOn(pdf, 50, 400)
    table.drawOn(pdf, 50, 400)
    pdf.save()
    return file_path

# --- APP INTERFACE ---
st.set_page_config(page_title="WIGI Time Manager", layout="wide")

if os.path.exists("wigi.png"):
    st.sidebar.image("wigi.png", use_container_width=True)

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("Welcome to WIGI Time Manager")
    tab1, tab2 = st.tabs(["Login", "Create New Account"])
    with tab1:
        u = st.text_input("Username")
        p = st.text_input("Password", type='password')
        if st.button("Access"):
            if c.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p)).fetchone():
                st.session_state['logged_in'], st.session_state['username'] = True, u
                st.rerun()
    with tab2:
        nu = st.text_input("New Username")
        np = st.text_input("New Password", type='password')
        if st.button("Register"):
            try:
                c.execute("INSERT INTO users VALUES (?,?)", (nu, np)); conn.commit()
                st.success("User created!")
            except: st.error("User exists.")
else:
    st.sidebar.markdown(f"### User: **{st.session_state['username']}**")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()
        
    choice = st.sidebar.selectbox("Navigation", ["Project Registration", "Time Tracker", "Weekly Reports"])
    
    if choice == "Project Registration":
        st.header("Project Management")
        with st.form("p_reg"):
            col1, col2 = st.columns(2)
            num, name = col1.text_input("Project ID"), col2.text_input("Project Name")
            hours = st.number_input("Allocated Time", min_value=0.0)
            if st.form_submit_button("Save"):
                try:
                    c.execute("INSERT INTO projects VALUES (?,?,?,?)", (num, name, hours, hours)); conn.commit()
                    st.success("Registered!"); st.rerun()
                except: st.error("Error: ID exists.")
        st.dataframe(pd.read_sql("SELECT * FROM projects", conn), use_container_width=True)

    elif choice == "Time Tracker":
        st.header("Daily Time Tracking")
        projs = pd.read_sql("SELECT * FROM projects", conn)
        if not projs.empty:
            target = st.selectbox("Project", [f"{r['p_number']} - {r['name']}" for _, r in projs.iterrows()])
            p_id = target.split(" - ")[0]
            c1, c2 = st.columns(2)
            if c1.button("▶ START"):
                st.session_state['start_time'] = datetime.now()
                st.info(f"Started at {st.session_state['start_time'].strftime('%H:%M')}")
            if c2.button("■ STOP"):
                if 'start_time' in st.session_state:
                    diff = (datetime.now() - st.session_state['start_time']).total_seconds() / 3600
                    c.execute("INSERT INTO time_logs VALUES (?,?,?,?,?,?)", (st.session_state['username'], p_id, datetime.now().date(), st.session_state['start_time'], datetime.now(), diff))
                    c.execute("UPDATE projects SET remaining = remaining - ? WHERE p_number = ?", (diff, p_id)); conn.commit()
                    data = c.execute("SELECT remaining, allocated FROM projects WHERE p_number = ?", (p_id,)).fetchone()
                    st.success(f"Logged {diff:.2f}h. Remaining: {data[0]:.2f}h ({ (data[0]/data[1]*100):.1f}%)")
                    del st.session_state['start_time']
                else: st.warning("Start first")

    elif choice == "Weekly Reports":
        st.header("Weekly Performance")
        today = datetime.now().date()
        last_monday = today - timedelta(days=today.weekday())
        
        # Create fixed 7-day columns
        week_days = [last_monday + timedelta(days=i) for i in range(7)]
        
        logs = pd.read_sql("SELECT project_id, date, duration FROM time_logs WHERE date >= ?", conn, params=(last_monday,))
        
        # Build the table even if empty
        weekly_df = pd.DataFrame(index=pd.read_sql("SELECT p_number FROM projects", conn)['p_number'], columns=week_days).fillna(0.0)
        
        if not logs.empty:
            for _, row in logs.iterrows():
                log_date = datetime.strptime(str(row['date']), '%Y-%m-%d').date() if isinstance(row['date'], str) else row['date']
                if log_date in weekly_df.columns:
                    weekly_df.at[row['project_id'], log_date] += row['duration']
        
        # Rename columns for display: Mon, Tue...
        display_df = weekly_df.copy()
        display_df.columns = [d.strftime('%a (%d/%m)') for d in weekly_df.columns]
        st.dataframe(display_df, use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Export Weekly PDF"):
                w_path = generate_weekly_pdf(weekly_df, last_monday)
                with open(w_path, "rb") as f:
                    st.download_button("Download Weekly PDF", f, file_name=w_path)
        with col2:
            st.subheader("Project Balance PDF")
            p_names = pd.read_sql("SELECT name FROM projects", conn)['name'].tolist()
            if p_names:
                sel = st.selectbox("Select Project", p_names)
                if st.button("Export Project Status"):
                    rem = pd.read_sql("SELECT remaining FROM projects WHERE name=?", conn, params=(sel,)).iloc[0,0]
                    p_path = generate_project_pdf(sel, rem)
                    with open(p_path, "rb") as f:
                        st.download_button("Download Project PDF", f, file_name=p_path)