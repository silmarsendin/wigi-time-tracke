import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import os

# --- DATABASE SETUP ---
conn = sqlite3.connect('business_manager.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)')
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

# NOVA FUNÇÃO: Relatório detalhado solicitado
def generate_detailed_project_pdf(project_id, project_name, logs_df, remaining):
    file_path = f"detailed_report_{project_id}.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Project Usage Report: {project_name} ({project_id})", styles['Title']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    elements.append(Paragraph(f"Remaining Balance: {remaining:.2f} hours", styles['Normal']))
    elements.append(Spacer(1, 24))

    if not logs_df.empty:
        data = [["Date", "Start Time", "End Time", "Duration (h)"]]
        for _, row in logs_df.iterrows():
            # Tratamento de formato de data/hora para evitar erros de visualização
            st_t = row['start_time'].split('.')[0] if isinstance(row['start_time'], str) else row['start_time'].strftime('%H:%M:%S')
            en_t = row['end_time'].split('.')[0] if isinstance(row['end_time'], str) else row['end_time'].strftime('%H:%M:%S')
            data.append([str(row['date']), st_t, en_t, f"{row['duration']:.2f}"])

        table = Table(data, colWidths=[100, 150, 150, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No logs found for this project.", styles['Normal']))

    doc.build(elements)
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
                    c.execute("INSERT INTO projects VALUES (?,?,?,?,?)", (num, name, hours, hours, current_user))
                    conn.commit(); st.success("Project Registered!"); st.rerun()
                except: st.error("Project ID already exists.")
        
        my_projs = pd.read_sql("SELECT p_number, name, allocated, remaining FROM projects WHERE owner=?", conn, params=(current_user,))
        st.dataframe(my_projs, use_container_width=True)

    elif choice == "Time Tracker":
        st.header("Work Logging")
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
                    st.success(f"Logged {diff:.2f}h. Balance: {data[0]:.2f}h")
                    del st.session_state['start_time']

    elif choice == "Weekly Reports":
        st.header("Your Weekly Summary")
        today = datetime.now().date()
        last_monday = today - timedelta(days=today.weekday())
        week_days = [last_monday + timedelta(days=i) for i in range(7)]
        
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
        
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Export Weekly PDF"):
                w_path = generate_weekly_pdf(weekly_df, last_monday)
                with open(w_path, "rb") as f: st.download_button("Download Weekly PDF", f, file_name=w_path)
        
        with col_b:
            # Interface para o novo relatório detalhado por projeto
            st.write("---")
            st.subheader("Detailed Project Report")
            my_p_info = pd.read_sql("SELECT p_number, name, remaining FROM projects WHERE owner=?", conn, params=(current_user,))
            if not my_p_info.empty:
                sel_proj = st.selectbox("Project for Detailed PDF", [f"{r['p_number']} - {r['name']}" for _, r in my_p_info.iterrows()], key="detailed_sel")
                p_id_sel = sel_proj.split(" - ")[0]
                p_name_sel = sel_proj.split(" - ")[1]
                p_rem_sel = my_p_info[my_p_info['p_number'] == p_id_sel]['remaining'].values[0]

                if st.button("Generate Detailed PDF"):
                    detailed_logs = pd.read_sql("SELECT date, start_time, end_time, duration FROM time_logs WHERE project_id = ? AND user = ? ORDER BY date DESC", 
                                                conn, params=(p_id_sel, current_user))
                    pdf_path = generate_detailed_project_pdf(p_id_sel, p_name_sel, detailed_logs, p_rem_sel)
                    with open(pdf_path, "rb") as f:
                        st.download_button("Download Detailed PDF", f, file_name=pdf_path)
