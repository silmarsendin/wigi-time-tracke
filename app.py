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

# =========================================================
# PATH SETUP (PERSISTENT)
# =========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "business_manager.db")

# =========================================================
# DATABASE CONNECTION
# =========================================================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            is_working INTEGER DEFAULT 0,
            start_time_db TEXT,
            active_project_id TEXT,
            manager INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            p_number TEXT PRIMARY KEY,
            name TEXT,
            allocated REAL,
            remaining REAL,
            owner TEXT,
            finished INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS time_logs (
            user TEXT,
            project_id TEXT,
            date DATE,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration REAL
        )
    """)

    c.execute("""
        INSERT OR IGNORE INTO users (username, password, manager)
        VALUES ('admin', 'admin123', 1)
    """)

    conn.commit()

# Inicializa o banco apenas uma vez por sessão
if "db_initialized" not in st.session_state:
    init_db()
    st.session_state["db_initialized"] = True

# =========================================================
# STREAMLIT CONFIG
# =========================================================
st.set_page_config(page_title="WIGI Time Manager", layout="wide")

# =========================================================
# LOGIN STATE
# =========================================================
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# =========================================================
# LOGIN / REGISTER
# =========================================================
if not st.session_state["logged_in"]:
    st.title("WIGI Time Manager")

    tab1, tab2 = st.tabs(["Login", "New User"])

    with tab1:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")

        if st.button("Access"):
            user = c.execute(
                "SELECT username, manager FROM users WHERE username=? AND password=?",
                (u, p)
            ).fetchone()

            if user:
                st.session_state["logged_in"] = True
                st.session_state["username"] = user[0]
                st.session_state["is_manager"] = bool(user[1])
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        new_u = st.text_input("New Username")
        new_p = st.text_input("New Password", type="password")
        is_m = st.toggle("Is Manager?", value=False)

        if st.button("Register"):
            try:
                c.execute(
                    "INSERT INTO users (username, password, manager) VALUES (?, ?, ?)",
                    (new_u, new_p, int(is_m))
                )
                conn.commit()
                st.success("User created successfully!")
            except:
                st.error("Username already exists")

# =========================================================
# MAIN APP
# =========================================================
else:
    # ================= CSS =================
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #262730; }
    [data-testid="stSidebar"] * { color: #FFFFFF; }

    /* Sidebar input text */
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] select,
    [data-testid="stSidebar"] textarea {
        color: #000000 !important;
    }

    /* Main buttons text */
    div[data-testid="stButton"] > button {
        color: #000000 !important;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

    logo_path = os.path.join(ASSETS_DIR, "wigi.png")
    if os.path.exists(logo_path):
        st.sidebar.image(logo_path, use_container_width=True)

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    user = st.session_state["username"]
    is_manager = st.session_state["is_manager"]

    menu = st.sidebar.selectbox(
        "Navigation",
        ["Project Registration", "Time Tracker", "Reports"]
    )

    # =====================================================
    # PROJECT REGISTRATION
    # =====================================================
    if menu == "Project Registration":
        st.header("Project Administration")

        with st.form("project_form"):
            p_id = st.text_input("Project ID")
            p_name = st.text_input("Project Name")
            hrs = st.number_input("Allocated Hours", min_value=0.0)
            finished = st.checkbox("Finished")

            if st.form_submit_button("Save Project"):
                try:
                    c.execute(
                        "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?)",
                        (p_id, p_name, hrs, hrs, user, int(finished))
                    )
                    conn.commit()
                    st.success("Project saved successfully!")
                except:
                    st.error("Project ID already exists")

        df = pd.read_sql(
            "SELECT * FROM projects" if is_manager else
            "SELECT * FROM projects WHERE owner=?",
            conn,
            params=() if is_manager else (user,)
        )

        st.dataframe(df, use_container_width=True)

    # =====================================================
    # TIME TRACKER
    # =====================================================
    elif menu == "Time Tracker":
        st.header("Time Tracker")

        projs = pd.read_sql(
            "SELECT p_number, name FROM projects WHERE owner=? AND finished=0",
            conn,
            params=(user,)
        )

        if not projs.empty:
            choice = st.selectbox(
                "Select Project",
                [f"{r.p_number} - {r.name}" for r in projs.itertuples()]
            )

            pid = choice.split(" - ")[0]
            col1, col2 = st.columns(2)

            if col1.button("▶ START"):
                c.execute(
                    "UPDATE users SET is_working=1, start_time_db=?, active_project_id=? WHERE username=?",
                    (datetime.now().isoformat(), pid, user)
                )
                conn.commit()
                st.success("Work started")

            if col2.button("■ STOP"):
                row = c.execute(
                    "SELECT start_time_db, active_project_id FROM users WHERE username=?",
                    (user,)
                ).fetchone()

                if row and row[0]:
                    start = datetime.fromisoformat(row[0])
                    diff = (datetime.now() - start).total_seconds() / 3600

                    c.execute(
                        "INSERT INTO time_logs VALUES (?, ?, ?, ?, ?, ?)",
                        (user, pid, datetime.now().date(), start, datetime.now(), diff)
                    )

                    c.execute(
                        "UPDATE projects SET remaining = remaining - ? WHERE p_number=?",
                        (diff, pid)
                    )

                    c.execute(
                        "UPDATE users SET is_working=0, start_time_db=NULL, active_project_id=NULL WHERE username=?",
                        (user,)
                    )

                    conn.commit()
                    st.success("Work stopped and logged")

    # =====================================================
    # REPORTS
    # =====================================================
    elif menu == "Reports":
        st.header("Reports")

        logs = pd.read_sql(
            "SELECT * FROM time_logs WHERE user=?",
            conn,
            params=(user,)
        )

        st.dataframe(logs, use_container_width=True)
