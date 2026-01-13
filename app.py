import streamlit as st
from database import init_db, run_query
from styles import apply_styles
from datetime import datetime

# Configuração Inicial
st.set_page_config(page_title="WIGI Time Manager", layout="wide")
apply_styles()

if "db_initialized" not in st.session_state:
    init_db()
    st.session_state["db_initialized"] = True

# --- LÓGICA DE LOGIN ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    # ... (Interface de login chamando run_query para validar)
    pass
else:
    # --- APP PRINCIPAL ---
    user = st.session_state["username"]
    
    menu = st.sidebar.selectbox("Navegação", ["Projetos", "Time Tracker", "Relatórios"])
    
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    if menu == "Projetos":
        # Chama funções do database.py
        pass
