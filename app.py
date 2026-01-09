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

# --- FUNÇÕES DE PDF ---
def generate_detailed_project_pdf(project_id, project_name, logs_df, remaining):
    file_path = f"detailed_report_{project_id}.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=A4, topMargin=1*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elements = []
    
    if os.path.exists("wigi.png"):
        try:
            logo = Image("wigi.png", width=4*cm, height=2*cm)
            logo.hAlign = 'CENTER'
            elements.append(logo)
            elements.append(Spacer(1, 0.5*cm))
        except: pass

    elements.append(Paragraph(f"Project Usage Report: {project_name}", styles['Title']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Remaining Balance: {remaining:.2f} hours", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    if not logs_df.empty:
        data = [["Date", "Start", "End", "Duration (h)"]]
        for _, row in logs_df.iterrows():
            data.append([str(row['date']), str(row['start_time'])[:16], str(row['end_time'])[:16], f"{row['duration']:.2f}"])
        table = Table(data, colWidths=[3.5*cm, 4.5*cm, 4.5*cm, 3.5*cm])
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey), ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        elements.append(table)
    doc.build(elements)
    return file_path

def generate_weekly_pdf(df, start_date):
    file_path = "weekly_summary.pdf"
    pdf = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4
    if os.path.exists("wigi.png"):
        try: pdf.drawImage("wigi.png", (width/2)-2*cm, height-1.8*cm, width=4*cm, preserveAspectRatio=True)
        except: pass
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(width/2, height-2.8*cm, "TIME SHEET")
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(1.5*cm, height-4.0*cm, f"Emp Name: {st.session_state.get('username', 'User')}")
    pdf.drawString(width-6*cm, height-4.5*cm, f"Week Ending: {start_date.strftime('%m/%d/%y')}")
    headers = ["Job #", "Job Name", "M", "T", "W", "T", "F", "S", "S", "RT"]
    data = [headers]
    for p_id, row in df.iterrows():
        p_info = c.execute("SELECT name FROM projects WHERE p_number=?", (p_id,)).fetchone()
        line = [p_id, p_info[0] if p_info else "N/A"]
        line.extend([f"{v:.1f}" if v > 0 else "" for v in row.values])
        line.append(f"{row.sum():.1f}")
        data.append(line)
    table = Table(data, colWidths=[2.2*cm, 4.4*cm, 1.1*cm, 1.1*cm, 1.1*cm, 1.1*cm, 1.1*cm, 1.1*cm, 1.1*cm, 1.4*cm])
    table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('FONTSIZE', (0, 0), (-1, -1), 8), ('ALIGN', (2,0), (-1,-1), 'CENTER')]))
    t_w, t_h = table.wrap(width, height)
    table.drawOn(pdf, 1.5*cm, height-6.5*cm-t_h)
    pdf.save()
    return file_path

# --- LOGIN ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("WIGI Time Manager")
    u = st.text_input("Username")
    p = st.text_input("Password", type='password')
    if st.button("Access"):
        if c.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p)).fetchone():
            st.session_state['logged_in'], st.session_state['username'] = True, u
            st.rerun()
else:
    if os.path.exists("wigi.png"): st.sidebar.image("wigi.png", use_container_width=True)
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()
    
    current_user = st.session_state['username']
    choice = st.sidebar.selectbox("Navigation", ["Project Registration", "Time Tracker", "Reports"])

    if choice == "Project Registration":
        st.header("My Projects")
        with st.form("p_reg"):
            col1, col2 = st.columns(2)
            num, name = col1.text_input("Project ID"), col2.text_input("Project Name")
            hours = st.number_input("Allocated Time", min_value=0.0)
            if st.form_submit_button("Save Project"):
                try:
                    c.execute("INSERT INTO projects VALUES (?,?,?,?,?)", (num, name, hours, hours, current_user))
                    conn.commit(); st.success("Project Registered!"); st.rerun()
                except: st.error("Project ID already exists.")
        my_projs = pd.read_sql("SELECT p_number, name, allocated, remaining FROM projects WHERE owner=?", conn, params=(current_user,))
        st.dataframe(my_projs, use_container_width=True)

    elif choice == "Time Tracker":
        st.header("Work Logging")
        user_data = c.execute("SELECT is_working, start_time_db, active_project_id FROM users WHERE username=?", (current_user,)).fetchone()
        working_now, start_time_str, active_p_id = bool(user_data[0]), user_data[1], user_data[2]

        # Estilo Dinâmico: Apenas se estiver "Working"
        if working_now:
            st.markdown("""<style>
                div[data-testid="stToggle"] label p { color: #1E90FF !important; font-weight: bold; }
                div[data-testid="stToggle"] div[aria-checked="true"] { background-color: #1E90FF !important; }
            </style>""", unsafe_allow_html=True)
            p_data = c.execute("SELECT name FROM projects WHERE p_number=?", (active_p_id,)).fetchone()
            st.markdown(f'<div style="background-color:#E3F2FD; padding:15px; border-radius:8px; border-left:6px solid #1E90FF; color:#1E90FF; margin-bottom:10px;">🔵 <b>Status:</b> Working on Project: <b>{p_data[0] if p_data else "Unknown"}</b></div>', unsafe_allow_html=True)
            t_label = "Working"
        else:
            t_label = "Available"

        st.toggle(t_label, value=working_now, disabled=True)
        projs = pd.read_sql("SELECT p_number, name FROM projects WHERE owner=?", conn, params=(current_user,))
        
        if not projs.empty:
            target = st.selectbox("Select Project", [f"{r['p_number']} - {r['name']}" for _, r in projs.iterrows()], key="auto_sel")
            p_id = target.split(" - ")[0]
            c1, c2 = st.columns(2)
            if c1.button("▶ START", use_container_width=True):
                c.execute("UPDATE users SET is_working=1, start_time_db=?, active_project_id=? WHERE username=?", (datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'), p_id, current_user))
                conn.commit(); st.rerun()
            if c2.button("■ STOP", use_container_width=True):
                if working_now and start_time_str:
                    start_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S.%f')
                    diff = (datetime.now() - start_dt).total_seconds() / 3600
                    c.execute("INSERT INTO time_logs VALUES (?,?,?,?,?,?)", (current_user, active_p_id, datetime.now().date(), start_dt, datetime.now(), diff))
                    c.execute("UPDATE projects SET remaining = remaining - ? WHERE p_number = ?", (diff, active_p_id))
                    c.execute("UPDATE users SET is_working=0, start_time_db=NULL, active_project_id=NULL WHERE username=?", (current_user,))
                    conn.commit(); st.rerun()

        st.divider()
        st.subheader("Manual Adjustment")
        with st.form("manual_adj"):
            sel_man = st.selectbox("Project", [f"{r['p_number']} - {r['name']}" for _, r in projs.iterrows()])
            m_hrs = st.number_input("Hours", min_value=0.1)
            m_act = st.radio("Action", ["Add Work", "Remove Work"])
            if st.form_submit_button("Apply"):
                val = m_hrs if "Add" in m_act else -m_hrs
                c.execute("UPDATE projects SET remaining = remaining - ? WHERE p_number=?", (val, sel_man.split(" - ")[0]))
                conn.commit(); st.success("Updated!"); st.rerun()

    elif choice == "Reports":
        st.header("Reports & Summaries")
        today = datetime.now().date()
        last_monday = today - timedelta(days=today.weekday())
        logs = pd.read_sql("SELECT project_id, date, duration FROM time_logs WHERE date >= ? AND user = ?", conn, params=(last_monday, current_user))
        my_p_list = pd.read_sql("SELECT p_number FROM projects WHERE owner=?", conn, params=(current_user,))['p_number'].tolist()
        weekly_df = pd.DataFrame(index=my_p_list, columns=[last_monday + timedelta(days=i) for i in range(7)]).fillna(0.0)
        for _, row in logs.iterrows():
            l_date = datetime.strptime(str(row['date']), '%Y-%m-%d').date() if isinstance(row['date'], str) else row['date']
            if l_date in weekly_df.columns and row['project_id'] in weekly_df.index:
                weekly_df.at[row['project_id'], l_date] += row['duration']
        st.dataframe(weekly_df.rename(columns=lambda d: d.strftime('%a %d/%m')), use_container_width=True)
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Export Weekly PDF"):
                w_path = generate_weekly_pdf(weekly_df, last_monday)
                with open(w_path, "rb") as f: st.download_button("Download Weekly PDF", f, file_name=w_path)
        with col_b:
            my_p_info = pd.read_sql("SELECT p_number, name, remaining FROM projects WHERE owner=?", conn, params=(current_user,))
            if not my_p_info.empty:
                sel_p = st.selectbox("Project for Detailed PDF", [f"{r['p_number']} - {r['name']}" for _, r in my_p_info.iterrows()])
                if st.button("Generate Detailed PDF"):
                    p_id_sel, p_name_sel = sel_p.split(" - ")[0], sel_p.split(" - ")[1]
                    p_rem = my_p_info[my_p_info['p_number'] == p_id_sel]['remaining'].values[0]
                    d_logs = pd.read_sql("SELECT date, start_time, end_time, duration FROM time_logs WHERE project_id = ? AND user = ?", conn, params=(p_id_sel, current_user))
                    pdf_p = generate_detailed_project_pdf(p_id_sel, p_name_sel, d_logs, p_rem)
                    with open(pdf_p, "rb") as f: st.download_button("Download Detailed PDF", f, file_name=pdf_p)
