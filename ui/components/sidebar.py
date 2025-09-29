# --- filepath: video_narrative_processor/ui/components/sidebar.py
import streamlit as st

DEFAULT_PROMPT = (
        """CONTEXTO: Eres experto en guiones virales para redes sociales.\n\n"""
        "TAREA: Reescribe la narrativa respetando hechos (nombres/fechas/lugares) y cambia el estilo. Quiero una versión nueva, con más gancho, NO una paráfrasis superficial.\n"
        "RESTRICCIONES: .\n"
        "   - Evita palabras que desmoneticen: usa eufemismos/rodeos para temas sensibles (autolesiones, sustancias ilícitas, violencia explícita, fallecimientos, lesiones graves, discriminación, extremismos, etc.).\n"
        "   - Mantén nombres, lugares y fechas.\n"
        "   - Estilo: dinámico, con suspenso, ritmo juvenil.\n"
        "   - Longitud: ENTRE {MIN_WORDS} y {MAX_WORDS} palabras.\n"
        "INSTRUCCIONES:\n"
        "   - Puedes reordenar la narracion y sus eventos (narrar en otro orden)."
        "   - Puedes Incluir una frase de enganche al inicio y un cierre que invite a interactuar."
        "   - Evita replicar exactamente el orden del texto original"
        "LONGITUD: ENTRE {MIN_WORDS} y {MAX_WORDS} palabras.\n\n"
        "SALIDA JSON estricto, sin texto extra: {\"titulo\": str, \"cuerpo\": str}"
    )



def app_controls():
    # Modelo como radio, por defecto ChatGPT 5
    model = st.sidebar.radio("Modelo de IA", ["ChatGPT 5", "Claude 4"], index=0)
    # Idioma
    lang = st.sidebar.selectbox("Idioma", ["ES", "ES/EN"], index=0)
    # Prompt editable con placeholders
    st.sidebar.caption("Si editas el prompt, conserva {MIN_WORDS} y {MAX_WORDS} para indicar el tamaño y deja la instruccion final de 'SALIDA JSON ESTRICTO: {\"titulo\": str, \"cuerpo\": str}'.")
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
