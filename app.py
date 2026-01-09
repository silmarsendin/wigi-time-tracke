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

# --- CONFIGURAÇÃO DA BASE DE DADOS ---
conn = sqlite3.connect('business_manager.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, is_working INTEGER DEFAULT 0)')
    c.execute('''CREATE TABLE IF NOT EXISTS projects 
                 (p_number TEXT PRIMARY KEY, name TEXT, allocated FLOAT, remaining FLOAT, owner TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS time_logs 
                 (user TEXT, project_id TEXT, date DATE, start_time TIMESTAMP, end_time TIMESTAMP, duration FLOAT)''')
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES ('admin', 'admin123')")
    
    # Garantir que a coluna is_working existe (migração simples)
    try:
        c.execute("ALTER TABLE users ADD COLUMN is_working INTEGER DEFAULT 0")
    except: pass
    conn.commit()

init_db()

# --- FUNÇÕES DE PDF (Mantidas conforme sua última solicitação) ---
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
    elements.append(Paragraph(f"Project Usage Report: {project_name} ({project_id})", styles['Title']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    elements.append(Paragraph(f"Remaining Balance: {remaining:.2f} hours", styles['Normal']))
    elements.append(Spacer(1, 24))
    if not logs_df.empty:
        data = [["Date", "Start", "End", "Duration (h)"]]
        for _, row in logs_df.iterrows():
            def format_time(t):
                ts = str(t)
                return ts.split(' ')[1][:5] if ' ' in ts else ts[:5]
            data.append([str(row['date']), format_time(row['start_time']), format_time(row['end_time']), f"{row['duration']:.2f}"])
        table = Table(data, colWidths=[3.5*cm, 4.5*cm, 4.5*cm, 3.5*cm])
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold')]))
        elements.append(table)
    doc.build(elements)
    return file_path

def generate_weekly_pdf(df, start_date):
    file_path = "weekly_summary.pdf"
    pdf = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4
    if os.path.exists("wigi.png"):
        try: pdf.drawImage("wigi.png", (width/2) - 2*cm, height - 1.5*cm, width=4*cm, preserveAspectRatio=True, mask='auto')
        except: pass
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(width/2, height - 2.5*cm, "TIME SHEET")
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(1.5*cm, height - 4.0*cm, f"Emp Name: {st.session_state.get('username', 'User')}")
    pdf.drawString(width - 6*cm, height - 4.5*cm, f"Week Ending: {start_date.strftime('%m/%d/%y')}")
    headers = ["Job #", "Job Name", "M", "T", "W", "T", "F", "S", "S", "RT"]
    data = [headers]
    total_general = 0
    for p_id, row in df.iterrows():
        p_info = c.execute("SELECT name FROM projects WHERE p_number = ?", (p_id,)).fetchone()
        p_name = p_info[0] if p_info else "Unknown"
        line = [p_id, p_name]
        line.extend([f"{v:.1f}" if v > 0 else "" for v in row.values])
        row_total = row.sum(); line.append(f"{row_total:.1f}"); data.append(line); total_general += row_total
    table = Table(data, colWidths=[2.2*cm, 4.4*cm, 1.1*cm, 1.1*cm, 1.1*cm, 1.1*cm, 1.1*cm, 1.1*cm, 1.1*cm, 1.4*cm])
    table.setStyle(TableStyle([('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 8), ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('ALIGN', (2, 0), (-1, -1), 'CENTER'), ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey)]))
    t_width, t_height = table.wrap(width, height)
    table.drawOn(pdf, 1.5*cm, height - 6*cm - t_height)
    pdf.save()
    return file_path

# --- INTERFACE ---
st.set_page_config(page_title="WIGI Time Manager", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("WIGI Time Manager")
    t1, t2 = st.tabs(["Login", "Register"])
    with t1:
        u = st.text_input("Username")
        p = st.text_input("Password", type='password')
        if st.button("Access"):
            user_data = c.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p)).fetchone()
            if user_data:
                st.session_state['logged_in'], st.session_state['username'] = True, u
                st.rerun()
            else: st.error("Wrong credentials")
    # ... Registro omitido para brevidade ...
else:
    current_user = st.session_state['username']
    choice = st.sidebar.selectbox("Navigation", ["Project Registration", "Time Tracker", "Weekly Reports"])

    if choice == "Time Tracker":
        st.header("Work Logging")
        
        # BUSCAR ESTADO NO BANCO DE DADOS
        user_status = c.execute("SELECT is_working FROM users WHERE username=?", (current_user,)).fetchone()
        working_now = bool(user_status[0]) if user_status else False

        # EXIBIÇÃO DO TOGGLE (Apenas visualização)
        st.toggle("Working", value=working_now, disabled=True)
        
        projs = pd.read_sql("SELECT p_number, name FROM projects WHERE owner=?", conn, params=(current_user,))
        if not projs.empty:
            target = st.selectbox("Select Project", [f"{r['p_number']} - {r['name']}" for _, r in projs.iterrows()])
            p_id = target.split(" - ")[0]
            c1, c2 = st.columns(2)
            
            if c1.button("▶ START", use_container_width=True):
                st.session_state['start_time'] = datetime.now()
                c.execute("UPDATE users SET is_working = 1 WHERE username = ?", (current_user,))
                conn.commit()
                st.rerun()
                
            if c2.button("■ STOP", use_container_width=True):
                if 'start_time' in st.session_state:
                    diff = (datetime.now() - st.session_state['start_time']).total_seconds() / 3600
                    c.execute("INSERT INTO time_logs VALUES (?,?,?,?,?,?)", (current_user, p_id, datetime.now().date(), st.session_state['start_time'], datetime.now(), diff))
                    c.execute("UPDATE projects SET remaining = remaining - ? WHERE p_number = ? AND owner = ?", (diff, p_id, current_user))
                    c.execute("UPDATE users SET is_working = 0 WHERE username = ?", (current_user,))
                    conn.commit()
                    del st.session_state['start_time']
                    st.rerun()

    # ... Restante das abas (Registration / Reports) ...
