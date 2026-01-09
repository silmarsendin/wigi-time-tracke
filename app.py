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

# --- FUNÇÕES DE PDF (CORREÇÃO DEFINITIVA DO LOGO) ---

def generate_detailed_project_pdf(project_id, project_name, logs_df, remaining):
    file_path = f"detailed_report_{project_id}.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=A4, topMargin=1*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elements = []
    
    if os.path.exists("wigi.png"):
        try:
            # Carregamento simples para evitar distorção de cores/fundo preto
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
        try:
            # REMOVIDO mask='auto' para evitar que o logo fique preto
            # A imagem é desenhada respeitando a proporção original
            pdf.drawImage("wigi.png", (width/2)-2*cm, height-2.0*cm, width=4*cm, preserveAspectRatio=True)
        except: pass

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(width/2, height-3.0*cm, "TIME SHEET")
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(1.5*cm, height-4.2*cm, f"Emp Name: {st.session_state.get('username', 'User')}")
    pdf.drawString(width-6*cm, height-4.2*cm, f"Week Ending: {start_date.strftime('%m/%d/%y')}")
    
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
    
    pdf.setFont("Helvetica", 9)
    pdf.drawString(1.5*cm, 3*cm, "Emp. Signature: _______________________")
    pdf.drawString(width-8.5*cm, 3*cm, "Super. Signature: ______________________")
    
    pdf.save()
    return file_path

# --- O RESTANTE DO CÓDIGO (LOGIN, TRACKER, ETC) CONTINUA IGUAL ---
# ... (Mantenha o bloco 'if not st.session_state['logged_in']:' e abas de navegação anteriores)
