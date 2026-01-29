# --- filepath: video_narrative_processor/ui/auth.py
from pathlib import Path
import streamlit as st
import csv

USERS_FILE = Path("config/users.csv")

@st.cache_data
def load_users():
    """Load users with case-insensitive usernames.
    Returns dict with lowercase usernames as keys and tuples (original_username, password) as values.
    """
    users = {}
    if USERS_FILE.exists():
        with open(USERS_FILE, encoding="utf-8") as f:
            for row in csv.reader(f, delimiter=';'):
                if len(row) >= 2:
                    # Store with lowercase key but preserve original username
                    users[row[0].lower()] = (row[0], row[1])
    return users


def auth_panel() -> str | None:
    """Sidebar auth panel.
    - If not logged in: show login form.
    - If logged in: show green welcome and a Logout button.
    Returns username or None.
    """
    st.sidebar.image("config/logo.png", width="content")
    user = st.session_state.get("user")

    if user:
        extra = '💙' if user == 'naho' else ''
        st.sidebar.success(f"¡Bienvenid@, {user}{extra}!")
        if st.sidebar.button("Salir"):
            st.session_state.pop("user", None)
            st.rerun()
        return user

    st.sidebar.markdown("## Iniciar sesión")
    u = st.sidebar.text_input("Usuario", key="login_user")
    p = st.sidebar.text_input("Contraseña", type="password", key="login_pass")
    if st.sidebar.button("Entrar"):
        users = load_users()
        # Case-insensitive login: convert input to lowercase for comparison
        user_lower = u.lower()
        if user_lower in users:
            original_username, stored_password = users[user_lower]
            if stored_password == p:
                # Store the original username (with original case) in session
                st.session_state["user"] = original_username
                st.rerun()
            else:
                st.sidebar.error("Usuario o contraseña inválidos")
        else:
            st.sidebar.error("Usuario o contraseña inválidos")
    return None