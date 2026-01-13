import streamlit as st

def apply_styles():
    st.markdown("""
    <style>
        [data-testid="stSidebar"] { background-color: #262730; }
        /* ... todo o seu CSS aqui ... */
    </style>
    """, unsafe_allow_html=True)
