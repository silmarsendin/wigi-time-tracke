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
                  start_time_db TEXT, active_project_id TEXT, manager INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS projects 
                 (p_number TEXT PRIMARY KEY, name TEXT, allocated FLOAT, remaining FLOAT, owner TEXT, finished INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS time_logs 
                 (user TEXT, project_id TEXT, date DATE, start_time TIMESTAMP, end_time TIMESTAMP, duration FLOAT)''')
    
    cols_users = [column[1] for column in c.execute("PRAGMA table_info(users)")]
    if "is_working" not in cols_users: c.execute("ALTER TABLE users ADD COLUMN is_working INTEGER DEFAULT 0")
    if "start_time_db" not in cols_users: c.execute("ALTER TABLE users ADD COLUMN start_time_db TEXT")
    if "active_project_id" not in cols_users: c.execute("ALTER TABLE users ADD COLUMN active_project_id TEXT")
    if "manager" not in cols_users: c.execute("ALTER TABLE users ADD COLUMN manager INTEGER DEFAULT 0")
    
    cols_projects = [column[1] for column in c.execute("PRAGMA table_info(projects)")]
    if "finished" not in cols_projects: c.execute("ALTER TABLE projects ADD COLUMN finished INTEGER DEFAULT 0")
    
    c.execute("INSERT OR IGNORE INTO users (username, password, manager) VALUES ('admin', 'admin123', 1)")
    conn.commit()

init_db()

# --- APP CONFIG ---
st.set_page_config(page_title="WIGI Time Manager", layout="wide")

# --- FUNÇÕES DE PDF ---

def generate_detailed_project_pdf(project_id, project_name, logs_df, remaining):
    file_path = f"detailed_report_{project_id}.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=A4, topMargin=1*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elements = []
    
    if os.path.exists("wigi.png"):
        try:
            img = Image("wigi.png")
            width_target = 4*cm
            aspect = img.imageHeight / float(img.imageWidth)
            img.drawWidth = width_target
            img.drawHeight = width_target * aspect
            img.hAlign = 'CENTER'
            elements.append(img)
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

def generate_manager_report_pdf(df):
    file_path = "manager_global_report.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=A4, topMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elements = [Paragraph("Global Projects Status Report (Manager View)", styles['Title']), Spacer(1, 1*cm)]
    
    users = df['owner'].unique()
    for user in users:
        elements.append(Paragraph(f"User: {user}", styles['Heading2']))
        user_projs = df[df['owner'] == user]
        data = [["Project ID", "Name", "Allocated", "Remaining", "Finished"]]
        for _, row in user_projs.iterrows():
            is_fin = "Yes" if row['finished'] else "No"
            data.append([row['p_number'], row['name'], f"{row['allocated']:.2f}", f"{row['remaining']:.2f}", is_fin])
        
        table = Table(data, colWidths=[2.5*cm, 6.5*cm, 2.5*cm, 2.5*cm, 2*cm])
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey), ('GRID', (0, 0), (-1, -1), 0.5, colors.black)]))
        elements.append(table)
        elements.append(Spacer(1, 0.5*cm))
    
    doc.build(elements)
    return file_path

def generate_weekly_pdf(df, start_date):
    file_path = "weekly_summary.pdf"
    pdf = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4
    pdf.setFillColor(colors.black); pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(width/2, height-2.0*cm, "TIME SHEET")
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(1.5*cm, height-3.0*cm, f"Emp Name: {st.session_state.get('username', 'User')}")
    pdf.drawString(width-6*cm, height-3.0*cm, f"Week Ending: {start_date.strftime('%m/%d/%y')}")
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
    t_w, t_h = table.wrap(width, height); table.drawOn(pdf, 1.5*cm, height-5.5*cm-t_h); pdf.save()
    return file_path

# --- LOGIN / REGISTER INTERFACE ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("WIGI Time Manager")
    tab1, tab2 = st.tabs(["Login", "New User"])
    
    with tab1:
        u = st.text_input("Username", key="login_u")
        p = st.text_input("Password", type='password', key="login_p")
        if st.button("Access", key="btn_login"):
            user_record = c.execute("SELECT username, manager FROM users WHERE username=? AND password=?", (u, p)).fetchone()
            if user_record:
                st.session_state['logged_in'], st.session_state['username'] = True, user_record[0]
                st.session_state['is_manager'] = bool(user_record[1])
                st.rerun()
            else: st.error("Wrong credentials")
            
    with tab2:
        new_u = st.text_input("New Username", key="reg_u")
        new_p = st.text_input("New Password", type='password', key="reg_p")
        is_m_check = st.toggle("Is Manager?", value=False, key="reg_m")
        if st.button("Register", key="btn_reg"):
            try:
                m_val = 1 if is_m_check else 0
                c.execute("INSERT INTO users (username, password, manager) VALUES (?, ?, ?)", (new_u, new_p, m_val))
                conn.commit()
                st.success("User created! Please login.")
            except: st.error("Username already exists.")
else:
    # Sidebar styling
    st.markdown("""<style>
        [data-testid="stSidebar"] { background-color: #262730 !important; }
        [data-testid="stSidebar"] * { color: #FFFFFF !important; }
        div.stButton > button, div[data-testid="stSelectbox"] label p { color: #FFFFFF !important; }
    </style>""", unsafe_allow_html=True)
    
    if os.path.exists("wigi.png"): st.sidebar.image("wigi.png", use_container_width=True)
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False; st.rerun()
    
    current_user = st.session_state['username']
    is_manager = st.session_state.get('is_manager', False)
    choice = st.sidebar.selectbox("Navigation", ["Project Registration", "Time Tracker", "Reports"])

    if choice == "Project Registration":
        st.header("Projects Administration")
        with st.form("p_reg"):
            col1, col2 = st.columns(2)
            num, name = col1.text_input("Project ID"), col2.text_input("Project Name")
            hours = st.number_input("Allocated Time", min_value=0.0)
            is_finished = st.checkbox("Finished", value=False)
            
            if st.form_submit_button("Save Project"):
                try:
                    fin_val = 1 if is_finished else 0
                    c.execute("INSERT INTO projects VALUES (?,?,?,?,?,?)", (num, name, hours, hours, current_user, fin_val))
                    conn.commit(); st.success("Project Registered!"); st.rerun()
                except: st.error("Project ID already exists.")
        
        query = "SELECT * FROM projects" if is_manager else "SELECT * FROM projects WHERE owner=?"
        params = () if is_manager else (current_user,)
        my_projs = pd.read_sql(query, conn, params=params)
        if not is_manager: my_projs = my_projs.drop(columns=['owner'])
        st.dataframe(my_projs, use_container_width=True)

    elif choice == "Time Tracker":
        st.header("Work Logging")
        user_data = c.execute("SELECT is_working, start_time_db, active_project_id FROM users WHERE username=?", (current_user,)).fetchone()
        working_now, start_time_str, active_p_id = bool(user_data[0]), user_data[1], user_data[2]

        if working_now:
            st.markdown("""<style>
                div[data-testid="stToggle"] label p { color: #1E90FF !important; font-weight: bold !important; }
                div[data-testid="stToggle"] div[aria-checked="true"] { background-color: #1E90FF !important; }
            </style>""", unsafe_allow_html=True)
            p_data = c.execute("SELECT name FROM projects WHERE p_number=?", (active_p_id,)).fetchone()
            st.markdown(f'<div style="background-color:#E3F2FD; padding:15px; border-radius:8px; border-left:6px solid #1E90FF; color:#1E90FF; margin-bottom:10px;">🔵 <b>Status:</b> Working on Project: <b>{p_data[0] if p_data else "Unknown"}</b></div>', unsafe_allow_html=True)
            t_label = "Working"
        else: t_label = "Available"

        st.toggle(t_label, value=working_now, disabled=True)
        
        # Lista projetos não finalizados
        projs = pd.read_sql("SELECT p_number, name, finished FROM projects WHERE owner=? AND finished=0", conn, params=(current_user,))
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

            # --- FORMULÁRIO DE AJUSTE MANUAL E FINALIZAÇÃO ---
            st.divider()
            st.subheader("Manual Adjustment & Status")
            with st.form("manual_adj"):
                # Busca status atual de finalização para o projeto selecionado
                proj_status = c.execute("SELECT finished FROM projects WHERE p_number=?", (p_id,)).fetchone()
                m_hrs = st.number_input("Hours to adjust", min_value=0.0, step=0.1)
                m_act = st.radio("Action", ["Add Work (Reduces Remaining)", "Remove Work (Increases Remaining)"])
                m_fin = st.checkbox("Finalize Project", value=bool(proj_status[0]) if proj_status else False)
                
                if st.form_submit_button("Apply Changes"):
                    val = m_hrs if "Add" in m_act else -m_hrs
                    fin_val = 1 if m_fin else 0
                    c.execute("UPDATE projects SET remaining = remaining - ?, finished = ? WHERE p_number = ?", (val, fin_val, p_id))
                    conn.commit()
                    st.success("Project updated successfully!")
                    st.rerun()

    elif choice == "Reports":
        st.header("Reports & Summaries")
        if is_manager:
            st.subheader("🛠 Manager Special Report")
            if st.button("Generate Global Projects Report (PDF)"):
                all_p = pd.read_sql("SELECT * FROM projects ORDER BY owner", conn)
                m_path = generate_manager_report_pdf(all_p)
                with open(m_path, "rb") as f: st.download_button("Download Global Report", f, file_name=m_path)
            st.divider()

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
