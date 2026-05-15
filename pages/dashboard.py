import streamlit as st
from utils.auth import require_auth, get_current_user
from utils.db import get_user_projects

STATUS_BADGE = {
    "searching": ("🔍", "badge-blue", "Searching"),
    "analysing": ("🧠", "badge-amber", "Analysing"),
    "writing": ("✍️", "badge-amber", "Writing"),
    "done": ("✅", "badge-green", "Complete"),
}


def show():
    require_auth()
    user = get_current_user()

    st.markdown("## 🏠 Dashboard")
    st.markdown("Welcome back! Here are your research projects.")
    st.markdown("---")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("➕ New Project", use_container_width=True, type="primary"):
            st.session_state["current_page"] = "➕ New Project"
            st.rerun()

    with st.spinner("Loading projects..."):
        projects = get_user_projects(user.id)

    if not projects:
        st.info("No projects yet. Start by creating a new research project!")
        return

    st.markdown(f"**{len(projects)} project(s)**")
    st.markdown("<br>", unsafe_allow_html=True)

    for p in projects:
        icon, badge_cls, label = STATUS_BADGE.get(
            p.get("status", "searching"), ("🔍", "badge-gray", "Unknown")
        )
        with st.container():
            col1, col2, col3 = st.columns([4, 1, 1])
            with col1:
                st.markdown(f"### {p['title']}")
                st.markdown(f"**Objective:** {p['objective'][:120]}{'...' if len(p['objective']) > 120 else ''}")
                st.markdown(
                    f'<span class="badge {badge_cls}">{icon} {label}</span>',
                    unsafe_allow_html=True
                )
                st.caption(f"Updated: {p['updated_at'][:10]}")
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Open", key=f"open_{p['id']}", use_container_width=True):
                    st.session_state["current_project"] = p
                    st.session_state["current_page"] = "🔍 Search Papers"
                    st.rerun()
            with col3:
                st.markdown("<br>", unsafe_allow_html=True)
                status = p.get("status", "searching")
                if status == "analysing":
                    if st.button("→ Analyse", key=f"jump_{p['id']}", use_container_width=True):
                        st.session_state["current_project"] = p
                        st.session_state["current_page"] = "🧠 Analyse"
                        st.rerun()
                elif status in ["writing", "done"]:
                    if st.button("→ Write", key=f"jump_{p['id']}", use_container_width=True):
                        st.session_state["current_project"] = p
                        st.session_state["current_page"] = "✍️ Write"
                        st.rerun()
            st.markdown("---")
