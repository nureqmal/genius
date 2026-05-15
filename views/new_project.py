import streamlit as st
from utils.auth import require_auth, get_current_user
from utils.db import create_project


def show():
    require_auth()
    user = get_current_user()

    st.markdown("## ➕ New Research Project")
    st.markdown("Fill in your research details.")
    st.markdown("---")

    st.markdown("### 📌 Research Topic")
    topic = st.text_area(
        "What is your research about?",
        placeholder="e.g. Lipid Profiling using GCMS and Machine Learning for Halal Authentication",
        height=90,
        key="topic_input"
    )

    st.markdown("### 🎯 Research Objective")
    objective = st.text_area(
        "What do you aim to achieve?",
        placeholder="e.g. To develop a machine learning model using GC-MS lipid profiles to authenticate halal fats and oils",
        height=90,
        key="objective_input"
    )

    st.markdown("### 🔍 Research Gap *(optional)*")
    gap = st.text_area(
        "Any gap you have identified?",
        placeholder="e.g. Deep learning approaches for GC-MS lipid authentication remain underexplored.",
        height=80,
        key="gap_input"
    )

    st.markdown("---")

    if st.button("Start Research →", type="primary", use_container_width=True):
        if not topic.strip():
            st.error("Please enter a research topic.")
        elif not objective.strip():
            st.error("Please enter a research objective.")
        else:
            with st.spinner("Creating project..."):
                project = create_project(user.id, topic.strip(), objective.strip(), gap.strip())
            if project:
                st.session_state["current_project"] = project
                st.session_state["current_page"] = "🔍 Search Papers"
                st.success("Project created! Redirecting...")
                st.rerun()
            else:
                st.error("Failed to create project. Please try again.")
