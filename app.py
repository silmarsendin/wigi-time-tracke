import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import os

# =========================================================
# PATH SETUP (PERSISTENT)
# =========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "business_manager.db")

# =========================================================
# DATABASE
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
            start_time TEXT,
            end_time TEXT,
            duration REAL
        )
    """)
    c.execute(
        "INSERT OR IGNORE INTO users (username, password, manager) VALUES ('admin','admin123',1)"
    )
    conn.commit()

if "db_initialized" not in st.session_state:
    init_db()
    st.session_state["db_initialized"] = True

# =========================================================
# STREAMLIT CONFIG
# =========================================================
st.set_page_config(page_title="WIGI Time Manager", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# =========================================================
# LOGIN
# =========================================================
if not st.session_state["logged_in"]:
    st.title("WIGI Time Manager")

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

# =========================================================
# MAIN APP
# =========================================================
else:
    # ================= CSS DEFINITIVO =================
    st.markdown("""
    <style>
    /* Sidebar background */
    [data-testid="stSidebar"] {
        background-color: #262730;
    }

    /* Sidebar labels */
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label {
        color: #FFFFFF !important;
    }

    /* Sidebar inputs & selects */
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] select,
    [data-testid="stSidebar"] textarea {
        color: #000000 !important;
        background-color: #FFFFFF !important;
    }

    /* Selected value in selectbox */
    [data-testid="stSidebar"] div[role="combobox"] > div {
        color: #000000 !important;
    }

    /* Dropdown list */
    div[role="listbox"] * {
        color: #000000 !important;
    }

    /* ===== FIX DEFINITIVO: LOGOUT BUTTON TEXT ===== */
    [data-testid="stSidebar"] div[data-testid="stButton"] button {
        background-color: #FFFFFF !important;
    }

    [data-testid="stSidebar"] div[data-testid="stButton"] button span {
        color: #000000 !important;
        font-weight: bold;
    }

    /* Main page buttons */
    div[data-testid="stButton"] button span {
        color: #000001 !important;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

    # SIDEBAR
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    user = st.session_state["username"]

    menu = st.sidebar.selectbox(
        "Navigation",
        ["Project Registration", "Time Tracker", "Reports"]
    )

    # =====================================================
    # PROJECT REGISTRATION
    # =====================================================
    if menu == "Project Registration":
        st.header("Project Registration")

        with st.form("proj_form"):
            pid = st.text_input("Project ID")
            pname = st.text_input("Project Name")
            hrs = st.number_input("Allocated Hours", min_value=0.0)
            finished = st.checkbox("Finished")

            if st.form_submit_button("Save Project"):
                try:
                    c.execute(
                        "INSERT INTO projects VALUES (?,?,?,?,?,?)",
                        (pid, pname, hrs, hrs, user, int(finished))
                    )
                    conn.commit()
                    st.success("Project saved successfully")
                except:
                    st.error("Project ID already exists")

        df = pd.read_sql(
            "SELECT * FROM projects WHERE owner=?",
            conn,
            params=(user,)
        )
        st.dataframe(df, use_container_width=True)

    # =====================================================
    # TIME TRACKER
    # =====================================================
    elif menu == "Time Tracker":
        st.header("Time Tracker")

        user_data = c.execute(
            "SELECT is_working, start_time_db, active_project_id FROM users WHERE username=?",
            (user,)
        ).fetchone()

        working = bool(user_data[0])
        start_time = user_data[1]
        active_pid = user_data[2]

        st.toggle("Working" if working else "Available", value=working, disabled=True)

        projs = pd.read_sql(
            "SELECT p_number, name FROM projects WHERE owner=? AND finished=0",
            conn,
            params=(user,)
        )

        if not projs.empty:
            sel = st.selectbox(
                "Select Project",
                [f"{r.p_number} - {r.name}" for r in projs.itertuples()]
            )
            pid = sel.split(" - ")[0]

            col1, col2 = st.columns(2)

            if col1.button("▶ START"):
                c.execute(
                    "UPDATE users SET is_working=1, start_time_db=?, active_project_id=? WHERE username=?",
                    (datetime.now().isoformat(), pid, user)
                )
                conn.commit()
                st.rerun()

            if col2.button("■ STOP"):
                if working and start_time:
                    start = datetime.fromisoformat(start_time)
                    diff = (datetime.now() - start).total_seconds() / 3600

                    c.execute(
                        "INSERT INTO time_logs VALUES (?,?,?,?,?,?)",
                        (user, active_pid, datetime.now().date(),
                         start_time, datetime.now().isoformat(), diff)
                    )
                    c.execute(
                        "UPDATE projects SET remaining = remaining - ? WHERE p_number=?",
                        (diff, active_pid)
                    )
                    c.execute(
                        "UPDATE users SET is_working=0, start_time_db=NULL, active_project_id=NULL WHERE username=?",
                        (user,)
                    )
                    conn.commit()
                    st.rerun()

            # -------- MANUAL ADJUSTMENT --------
            st.divider()
            st.subheader("Manual Adjustment & Finalize")

            with st.form("manual_adj"):
                adj = st.number_input("Hours to adjust", min_value=0.0, step=0.1)
                action = st.radio("Action", ["Add Work", "Remove Work"])
                fin = st.checkbox("Finalize Project")

                if st.form_submit_button("Apply"):
                    delta = adj if action == "Add Work" else -adj
                    c.execute(
                        "UPDATE projects SET remaining = remaining - ?, finished=? WHERE p_number=?",
                        (delta, int(fin), pid)
                    )
                    conn.commit()
                    st.success("Project updated")
                    st.rerun()

    # =====================================================
    # REPORTS
    # =====================================================
    elif menu == "Reports":
        st.header("Reports")

        st.subheader("Time Logs")
        logs = pd.read_sql(
            "SELECT * FROM time_logs WHERE user=?",
            conn,
            params=(user,)
        )
        st.dataframe(logs, use_container_width=True)

        st.subheader("Projects Summary")
        projs = pd.read_sql(
            "SELECT p_number, name, allocated, remaining, finished FROM projects WHERE owner=?",
            conn,
            params=(user,)
        )
        st.dataframe(projs, use_container_width=True)
