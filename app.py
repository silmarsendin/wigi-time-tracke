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

# --- CONFIGURAÇÃO DA BASE DE DADOS ---
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

# --- FUNÇÕES PDF ---

# NOVA FUNÇÃO: Relatório detalhado de um projeto específico
def generate_detailed_project_pdf(project_id, project_name, logs_df, remaining):
    file_path = f"detalhado_{project_id}.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Título e Resumo
    elements.append(Paragraph(f"Relatório de Utilização: {project_name} ({project_id})", styles['Title']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Data de Extração: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    elements.append(Paragraph(f"Saldo Atual: {remaining:.2f} horas", styles['Normal']))
    elements.append(Spacer(1, 24))

    # Tabela de Dados
    if not logs_df.empty:
        # Formatar datas para exibição
        data = [["Data", "Início", "Fim", "Duração (h)"]]
        for _, row in logs_df.iterrows():
            d = row['date']
            st_t = datetime.strptime(row['start_time'], '%Y-%m-%d %H:%M:%S.%f').strftime('%H:%M') if isinstance(row['start_time'], str) else row['start_time'].strftime('%H:%M')
            en_t = datetime.strptime(row['end_time'], '%Y-%m-%d %H:%M:%S.%f').strftime('%H:%M') if isinstance(row['end_time'], str) else row['end_time'].strftime('%H:%M')
            data.append([d, st_t, en_t, f"{row['duration']:.2f}"])

        table = Table(data, colWidths=[100, 100, 100, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("Nenhum registro de tempo encontrado para este projeto.", styles['Normal']))

    doc.build(elements)
    return file_path

def generate_weekly_pdf(df, start_date):
    file_path = "weekly_summary.pdf"
    pdf = canvas.Canvas(file_path, pagesize=landscape(A4))
    data = [["Projeto"] + [col.strftime('%a %d/%m') for col in df.columns]]
    for index, row in df.iterrows():
        data.append([index] + [f"{v:.2f}" for v in row.values])
    table = Table(data)
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    table.wrapOn(pdf, 50, 400); table.drawOn(pdf, 50, 400); pdf.save()
    return file_path

# --- INTERFACE (RESUMO) ---
st.set_page_config(page_title="WIGI Time Manager", layout="wide")

# ... (Mantenha o código de Login e Registro original aqui) ...

if st.session_state.get('logged_in'):
    current_user = st.session_state['username']
    choice = st.sidebar.selectbox("Navegação", ["Registro de Projetos", "Time Tracker", "Relatórios"])

    # ... (Seções de Registro e Tracker permanecem similares) ...

    if choice == "Relatórios":
        st.header("Seus Relatórios")
        
        # Filtros e Tabela Semanal (Original melhorada)
        today = datetime.now().date()
        last_monday = today - timedelta(days=today.weekday())
        
        st.subheader("Resumo Semanal")
        logs = pd.read_sql("SELECT project_id, date, duration FROM time_logs WHERE date >= ? AND user = ?", conn, params=(last_monday, current_user))
        # ... (Lógica de montagem da weekly_df original) ...
        
        # SEÇÃO NOVA: Relatório Detalhado por Projeto
        st.divider()
        st.subheader("Exportar Relatório Detalhado por Projeto")
        
        my_p_info = pd.read_sql("SELECT p_number, name, remaining FROM projects WHERE owner=?", conn, params=(current_user,))
        if not my_p_info.empty:
            proj_choice = st.selectbox("Selecione o Projeto para PDF", [f"{r['p_number']} - {r['name']}" for _, r in my_p_info.iterrows()])
            p_id = proj_choice.split(" - ")[0]
            p_name = proj_choice.split(" - ")[1]
            p_rem = my_p_info[my_p_info['p_number'] == p_id]['remaining'].values[0]

            if st.button("Gerar PDF Detalhado"):
                # Busca todos os logs desse projeto específico
                proj_logs = pd.read_sql("SELECT date, start_time, end_time, duration FROM time_logs WHERE project_id = ? AND user = ? ORDER BY date DESC", 
                                        conn, params=(p_id, current_user))
                
                pdf_file = generate_detailed_project_pdf(p_id, p_name, proj_logs, p_rem)
                with open(pdf_file, "rb") as f:
                    st.download_button("Baixar Relatório Detalhado", f, file_name=pdf_file)
