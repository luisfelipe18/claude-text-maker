# --- filepath: video_narrative_processor/ui/components/sidebar.py
import streamlit as st

DEFAULT_PROMPT = (
    "CONTEXTO: Eres experto en guiones virales para redes sociales."
    "TAREA: Reescribe la narrativa respetando hechos (nombres/fechas/lugares) y cambia el estilo."
    "RESTRICCIONES: evita palabras que desmoneticen; mantén nombres, lugares y fechas."
    "ESTILO: dinámico, con suspenso y ritmo juvenil."
    "LONGITUD: ENTRE {MIN_WORDS} y {MAX_WORDS} palabras."
    "SALIDA JSON ESTRICTO: {\"titulo\": str, \"cuerpo\": str}"
)

def app_controls():
    # Modelo como radio, por defecto ChatGPT 5
    model = st.sidebar.radio("Modelo de IA", ["ChatGPT 5", "Claude 4"], index=0)
    # Idioma
    lang = st.sidebar.selectbox("Idioma", ["ES", "ES/EN"], index=0)
    # Prompt editable con placeholders
    st.sidebar.caption("Si editas el prompt, conserva {MIN_WORDS} y {MAX_WORDS}.")
    current = st.session_state.get("prompt_template", DEFAULT_PROMPT)
    prompt = st.sidebar.text_area("Prompt base", value=current, height=180, key="prompt_template")
    # Persist lightweight values for other modules if needed
    st.session_state["lang"] = lang
    st.session_state["model_choice"] = model
    return model, prompt, lang

def app_sidebar():
    from ..auth import auth_panel
    user = auth_panel()
    model, prompt, lang = (None, None, None)
    if user:
        model, prompt, lang = app_controls()
    return user, model, prompt, lang
