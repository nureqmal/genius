import streamlit as st
from utils.auth import is_authenticated

st.set_page_config(
    page_title="ResearchAI",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .stButton > button { border-radius: 8px; font-weight: 500; }
    .stButton > button[kind="primary"] { background: #6C63FF; border: none; color: white; }
    .paper-card { background: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 10px; padding: 1rem; margin-bottom: 0.75rem; }
    .badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: 500; }
    .badge-green { background: #d4edda; color: #155724; }
    .badge-blue { background: #cce5ff; color: #004085; }
    .badge-amber { background: #fff3cd; color: #856404; }
    .badge-gray { background: #e2e3e5; color: #383d41; }
    .section-box { background: #f0f0ff; border-left: 4px solid #6C63FF; padding: 1rem; border-radius: 0 8px 8px 0; margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

PAGES = [
    "🏠 Dashboard",
    "➕ New Project",
    "🔍 Search Papers",
    "🧠 Analyse",
    "✍️ Write",
    "📤 Export",
]

# Init nav state
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "🏠 Dashboard"

with st.sidebar:
    st.markdown("# 🔬 ResearchAI")
    st.markdown("---")

    if is_authenticated():
        user = st.session_state["user"]
        st.markdown(f"👤 **{user.email}**")
        st.markdown("---")

        for p in PAGES:
            is_active = st.session_state["current_page"] == p
            if st.button(p, use_container_width=True,
                         type="primary" if is_active else "secondary",
                         key=f"nav_{p}"):
                st.session_state["current_page"] = p
                st.rerun()

        st.markdown("---")
        if st.button("Sign Out", use_container_width=True):
            from utils.auth import sign_out
            sign_out()
            st.session_state["current_page"] = "🏠 Dashboard"
            st.rerun()
    else:
        st.session_state["current_page"] = "🏠 Dashboard"

# Page routing
if not is_authenticated():
    from pages.login import show
    show()
else:
    page = st.session_state["current_page"]
    if page == "🏠 Dashboard":
        from pages.dashboard import show
        show()
    elif page == "➕ New Project":
        from pages.new_project import show
        show()
    elif page == "🔍 Search Papers":
        from pages.search import show
        show()
    elif page == "🧠 Analyse":
        from pages.analyse import show
        show()
    elif page == "✍️ Write":
        from pages.write import show
        show()
    elif page == "📤 Export":
        from pages.export import show
        show()
