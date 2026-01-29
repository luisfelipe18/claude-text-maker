# --- filepath: video_narrative_processor/ui/main_app.py
import streamlit as st
from ui.components.sidebar import app_sidebar
from ui.components.generate_tab import generate_tab
from ui.components.explore_tab import explore_tab
from ui.components.image_creator import render_image_generator_tab
from ui.components.image_gallery_tab import render_image_gallery_tab
from ui.components.jobs_monitor_tab import jobs_monitor_tab


st.set_page_config(page_title="Narrativas", layout="wide")


user, model, prompt, lang = app_sidebar()


if not user:
    st.stop()


tabs = st.tabs(["Generar Narrativas", "📊 Monitor de Trabajos", "Explorar Narrativas", "Generar Imágenes", "Galería de Imágenes"])
with tabs[0]:
    generate_tab(user)
with tabs[1]:
    jobs_monitor_tab(user)
with tabs[2]:
    explore_tab(user)
with tabs[3]:
    render_image_generator_tab(user)
with tabs[4]:
    render_image_gallery_tab(user)
