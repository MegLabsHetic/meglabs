"""Authentication helpers for the Streamlit SaaS app."""

import streamlit as st

from config import TIERS
from utils.database import (
    authenticate_user,
    create_user,
    get_usage_today,
    get_user,
    log_usage,
    update_user_api_key,
)


def init_auth_state():
    """Initialize authentication session state."""
    defaults = {
        "authenticated": False,
        "user": None,
        "auth_page": "login",  # login | register
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def get_current_user() -> dict | None:
    """Get the currently authenticated user."""
    if st.session_state.get("authenticated") and st.session_state.get("user"):
        user = get_user(st.session_state["user"]["id"])
        if user:
            st.session_state["user"] = user
        return user
    return None


def get_user_tier_config(user: dict) -> dict:
    """Get the tier configuration for a user."""
    return TIERS.get(user.get("tier", "free"), TIERS["free"])


def check_feature_access(user: dict, feature: str) -> bool:
    """Check if a user has access to a feature."""
    tier_config = get_user_tier_config(user)
    return feature in tier_config["features"]


def check_rate_limit(user: dict, action: str) -> tuple[bool, str]:
    """Check if user is within rate limits. Returns (allowed, message)."""
    tier_config = get_user_tier_config(user)

    if action == "upload":
        limit = tier_config["max_uploads_per_day"]
        if limit == -1:
            return True, ""
        current = get_usage_today(user["id"], "upload")
        if current >= limit:
            return False, f"Limite d'uploads atteinte ({limit}/jour). Passez au plan superieur."
        return True, ""

    elif action == "ai_query":
        limit = tier_config["ai_queries_per_day"]
        if limit == -1:
            return True, ""
        current = get_usage_today(user["id"], "ai_query")
        if current >= limit:
            return False, f"Limite de requetes IA atteinte ({limit}/jour). Passez au plan superieur."
        return True, ""

    return True, ""


def render_login_page():
    """Render the login/register page. Returns True if user is authenticated."""
    init_auth_state()

    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        """
        <style>
            .auth-container {
                max-width: 450px;
                margin: 2rem auto;
                padding: 2rem;
            }
            .auth-title {
                text-align: center;
                font-size: 2rem;
                font-weight: 700;
                margin-bottom: 0.5rem;
            }
            .auth-subtitle {
                text-align: center;
                color: #888;
                margin-bottom: 2rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<p class="auth-title">\U0001f4ca DataAnalyst AI</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="auth-subtitle">Plateforme SaaS d\'analyse de donnees intelligente</p>',
            unsafe_allow_html=True,
        )

        tab_login, tab_register = st.tabs(["Connexion", "Inscription"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="votre@email.com")
                password = st.text_input("Mot de passe", type="password")
                submitted = st.form_submit_button("Se connecter", use_container_width=True)

                if submitted:
                    if not email or not password:
                        st.error("Veuillez remplir tous les champs.")
                    else:
                        user = authenticate_user(email, password)
                        if user:
                            st.session_state["authenticated"] = True
                            st.session_state["user"] = user
                            st.rerun()
                        else:
                            st.error("Email ou mot de passe incorrect.")

        with tab_register:
            with st.form("register_form"):
                reg_username = st.text_input("Nom d'utilisateur", placeholder="mon_pseudo")
                reg_email = st.text_input("Email", placeholder="votre@email.com", key="reg_email")
                reg_password = st.text_input("Mot de passe", type="password", key="reg_password")
                reg_password2 = st.text_input(
                    "Confirmer le mot de passe", type="password", key="reg_password2"
                )
                submitted = st.form_submit_button("Creer un compte", use_container_width=True)

                if submitted:
                    if not reg_username or not reg_email or not reg_password:
                        st.error("Veuillez remplir tous les champs.")
                    elif len(reg_password) < 6:
                        st.error("Le mot de passe doit contenir au moins 6 caracteres.")
                    elif reg_password != reg_password2:
                        st.error("Les mots de passe ne correspondent pas.")
                    else:
                        user = create_user(reg_email, reg_username, reg_password)
                        if user:
                            st.session_state["authenticated"] = True
                            st.session_state["user"] = user
                            st.success("Compte cree avec succes !")
                            st.rerun()
                        else:
                            st.error("Cet email ou nom d'utilisateur est deja utilise.")

        st.divider()
        st.markdown(
            "<small style='text-align:center;display:block;color:#888;'>"
            "En vous inscrivant, vous acceptez nos conditions d'utilisation.<br>"
            "Plan gratuit : 3 uploads/jour, 10 requetes IA/jour"
            "</small>",
            unsafe_allow_html=True,
        )

    return False


def render_user_sidebar(user: dict):
    """Render user info and settings in the sidebar."""
    tier_config = get_user_tier_config(user)

    st.markdown(f"**{user['username']}**")
    st.markdown(
        f"<small>Plan : <b>{tier_config['name']}</b></small>",
        unsafe_allow_html=True,
    )

    # Usage stats
    from utils.database import get_usage_stats
    stats = get_usage_stats(user["id"])

    upload_limit = tier_config["max_uploads_per_day"]
    ai_limit = tier_config["ai_queries_per_day"]

    upload_text = f"{stats['uploads_today']}/{upload_limit}" if upload_limit != -1 else f"{stats['uploads_today']}/\u221e"
    ai_text = f"{stats['ai_queries_today']}/{ai_limit}" if ai_limit != -1 else f"{stats['ai_queries_today']}/\u221e"

    col1, col2 = st.columns(2)
    col1.metric("Uploads", upload_text)
    col2.metric("IA", ai_text)

    # API Key
    st.divider()
    current_key = user.get("api_key_anthropic", "")
    api_key = st.text_input(
        "Cle API Anthropic",
        value=current_key,
        type="password",
        help="Entrez votre cle API Claude pour utiliser les fonctions IA",
    )
    if api_key != current_key:
        update_user_api_key(user["id"], api_key)
        st.session_state["user"]["api_key_anthropic"] = api_key

    if api_key:
        import os
        os.environ["ANTHROPIC_API_KEY"] = api_key

    # Upgrade button
    if user.get("tier", "free") == "free":
        st.divider()
        if st.button("Passer au plan Pro", use_container_width=True):
            st.session_state["show_pricing"] = True

    # Logout
    st.divider()
    if st.button("Se deconnecter", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
