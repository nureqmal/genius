import streamlit as st
from utils.auth import require_auth, get_current_user
from utils.db import create_project


def show():
    require_auth()
    user = get_current_user()

    st.markdown("## ➕ New Research Project")
    st.markdown("Fill in as much detail as possible — the more context you give, the better the AI can find relevant papers.")
    st.markdown("---")

    st.markdown("### 📌 Research Topic")
    topic = st.text_area(
        "What is your research about?",
        placeholder="e.g. Lipid Profiling using GCMS and Machine Learning Approaches for Halal Authentication of Fats and Oils",
        height=80,
        key="topic_input"
    )

    st.markdown("### 🎯 Research Objective")
    objective = st.text_area(
        "What do you aim to achieve or prove?",
        placeholder="e.g. To develop a machine learning model using GC-MS lipid profiles to authenticate halal fats and oils with high accuracy",
        height=80,
        key="objective_input"
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🔬 Field of Study")
        field = st.selectbox(
            "Select your research field:",
            ["Food Science & Technology", "Chemistry & Biochemistry",
             "Computer Science & AI", "Biomedical & Life Sciences",
             "Environmental Science", "Engineering", "Social Science",
             "Economics & Business", "Education", "Other"],
            key="field_input"
        )

    with col2:
        st.markdown("### 📅 Expected Publication Year Range")
        year_range = st.selectbox(
            "Papers from:",
            ["Last 5 years (recommended)", "Last 10 years", "Any year"],
            key="year_input"
        )

    st.markdown("### 🧪 Specific Methods / Tools / Substances")
    methods = st.text_input(
        "List specific techniques, instruments, materials, or algorithms involved:",
        placeholder="e.g. GC-MS, FAME, PCA, SVM, lipid profiling, fatty acid methyl esters",
        key="methods_input"
    )

    st.markdown("### 🌍 Application Domain")
    domain = st.text_input(
        "What is the real-world application or context?",
        placeholder="e.g. Halal food certification, food fraud detection, edible oil authentication",
        key="domain_input"
    )

    st.markdown("### 🔍 Research Gap *(optional)*")
    gap = st.text_area(
        "Any gap you have identified in existing literature?",
        placeholder="e.g. Most studies use traditional chemometric methods; deep learning approaches for GC-MS lipid authentication remain underexplored.",
        height=80,
        key="gap_input"
    )

    st.markdown("### 💡 Additional Context *(optional)*")
    context = st.text_area(
        "Anything else the AI should know about your research?",
        placeholder="e.g. Focus on Malaysian halal standards, comparing lard vs plant-based oils, targeting journal submission to Food Chemistry or LWT.",
        height=80,
        key="context_input"
    )

    st.markdown("---")

    if st.button("Start Research →", type="primary", use_container_width=True):
        if not topic.strip():
            st.error("Please enter a research topic.")
        elif not objective.strip():
            st.error("Please enter a research objective.")
        else:
            # Build enriched objective with all context
            enriched_objective = objective.strip()
            if methods.strip():
                enriched_objective += f" | Methods/Tools: {methods.strip()}"
            if domain.strip():
                enriched_objective += f" | Application: {domain.strip()}"
            if field:
                enriched_objective += f" | Field: {field}"
            if context.strip():
                enriched_objective += f" | Context: {context.strip()}"

            with st.spinner("Creating project..."):
                project = create_project(
                    user.id,
                    topic.strip(),
                    enriched_objective,
                    gap.strip()
                )

            if project:
                st.session_state["current_project"] = project
                st.session_state["current_page"] = "🔍 Search Papers"
                st.success("Project created! Redirecting to paper search...")
                st.rerun()
            else:
                st.error("Failed to create project. Please try again.")
