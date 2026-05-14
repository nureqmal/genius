import os
from supabase import create_client, Client
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, "")


SUPABASE_URL = _get_secret("SUPABASE_URL")
SUPABASE_ANON_KEY = _get_secret("SUPABASE_ANON_KEY")


@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def sign_up(email: str, password: str):
    sb = get_supabase()
    try:
        res = sb.auth.sign_up({"email": email, "password": password})
        return res.user, None
    except Exception as e:
        return None, str(e)


def sign_in(email: str, password: str):
    sb = get_supabase()
    try:
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
        return res.user, res.session, None
    except Exception as e:
        return None, None, str(e)


def sign_out():
    sb = get_supabase()
    try:
        sb.auth.sign_out()
        for key in ["user", "session", "current_project"]:
            if key in st.session_state:
                del st.session_state[key]
    except Exception:
        pass


def get_current_user():
    return st.session_state.get("user", None)


def is_authenticated():
    return "user" in st.session_state and st.session_state["user"] is not None


def require_auth():
    if not is_authenticated():
        st.warning("Please log in to continue.")
        st.stop()
