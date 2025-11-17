# --- filepath: video_narrative_processor/ui/main_app.py
import streamlit as st
from ui.components.sidebar import app_sidebar
from ui.components.generate_tab import generate_tab
from ui.components.explore_tab import explore_tab


st.set_page_config(page_title="Narrativas", layout="wide")


user, model, prompt, lang = app_sidebar()


if not user:
    st.stop()


tabs = st.tabs(["Generar Narrativas", "Explorar Narrativas"])
with tabs[0]:
    generate_tab(user)
with tabs[1]:
    explore_tab(user)
