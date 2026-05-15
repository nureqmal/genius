import streamlit as st
from utils.auth import require_auth
from utils.db import get_research_pool, get_drafts, get_project
from utils.citations import generate_all_citations
from utils.export import export_docx, export_pdf

SECTION_ORDER = [
    ("introduction", "Introduction"),
    ("literature_review", "Literature Review"),
    ("methodology", "Methodology"),
    ("results_discussion", "Results and Discussion"),
    ("conclusion", "Conclusion"),
]


def show():
    require_auth()

    project = st.session_state.get("current_project")
    if not project:
        st.warning("No active project.")
        return

    project = get_project(project["id"]) or project

    st.markdown("## 📤 Export")
    st.markdown(f"**Project:** {project['title']}")
    st.markdown("---")

    pool = get_research_pool(project["id"])
    confirmed = [p for p in pool if p.get("confirmed")]
    drafts = get_drafts(project["id"])

    if not confirmed:
        st.warning("No confirmed papers. Please complete the Analysis step first.")
        return

    if not drafts:
        st.warning("No written sections found. Please complete the Writing step first.")
        return

    done_sections = {k: v for k, v in drafts.items() if v and v.strip()}
    st.markdown(f"**{len(done_sections)}/{len(SECTION_ORDER)} sections ready** · "
                f"**{len(confirmed)} papers** in reference list")

    st.markdown("### Citation Format")
    cite_format = st.radio("Select citation style:", ["APA 7th", "IEEE", "MLA"], horizontal=True)
    format_key = {"APA 7th": "apa", "IEEE": "ieee", "MLA": "mla"}[cite_format]

    with st.expander("📚 Preview Reference List"):
        with st.spinner("Generating references..."):
            refs = generate_all_citations(confirmed, format_key)
        for i, ref in enumerate(refs, 1):
            st.markdown(f"{i}. {ref}")

    st.markdown("---")
    st.markdown("### Document Title")
    doc_title = st.text_input("Title of your paper/thesis:", value=project["title"])

    st.markdown("---")
    st.markdown("### Download")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Word Document (.docx)**")
        st.caption("Editable — recommended for final revisions")
        if st.button("Generate Word Document", use_container_width=True, type="primary"):
            with st.spinner("Generating .docx..."):
                refs = generate_all_citations(confirmed, format_key)
                docx_bytes = export_docx(
                    title=doc_title, topic=project["topic"],
                    sections=done_sections, references=refs, style=format_key,
                )
            safe_title = "".join(c for c in project["title"][:40] if c.isalnum() or c in " _-").strip()
            st.download_button(
                label="⬇️ Download .docx", data=docx_bytes,
                file_name=f"{safe_title or 'research_paper'}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )

    with col2:
        st.markdown("**PDF Document (.pdf)**")
        st.caption("Print-ready — for sharing or submission")
        if st.button("Generate PDF", use_container_width=True, type="primary"):
            with st.spinner("Generating PDF..."):
                refs = generate_all_citations(confirmed, format_key)
                pdf_bytes = export_pdf(title=doc_title, sections=done_sections, references=refs)
            safe_title = "".join(c for c in project["title"][:40] if c.isalnum() or c in " _-").strip()
            st.download_button(
                label="⬇️ Download PDF", data=pdf_bytes,
                file_name=f"{safe_title or 'research_paper'}.pdf",
                mime="application/pdf", use_container_width=True,
            )

    st.markdown("---")
    st.markdown("### Paper Preview")
    for key, title in SECTION_ORDER:
        content = done_sections.get(key, "")
        if content:
            with st.expander(f"**{title}**"):
                st.write(content)
