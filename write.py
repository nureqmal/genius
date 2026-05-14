import streamlit as st
from utils.auth import require_auth
from utils.ai import write_section
from utils.db import get_research_pool, get_drafts, save_draft, update_project_status, get_project

SECTIONS = [
    ("introduction", "1. Introduction"),
    ("literature_review", "2. Literature Review"),
    ("methodology", "3. Methodology"),
    ("results_discussion", "4. Results & Discussion"),
    ("conclusion", "5. Conclusion"),
]

STYLE_OPTIONS = {
    "Formal Academic": "formal_academic",
    "Semi-formal": "semi_formal",
    "Humanized": "humanized",
}

STYLE_DESC = {
    "Formal Academic": "Third-person, passive voice, discipline-specific language.",
    "Semi-formal": "Balanced tone — readable but scholarly.",
    "Humanized": "Natural flow, active voice. Doesn't sound like AI wrote it.",
}


def show():
    require_auth()

    project = st.session_state.get("current_project")
    if not project:
        st.warning("No active project.")
        return

    project = get_project(project["id"]) or project
    st.session_state["current_project"] = project

    st.markdown("## ✍️ Writing Assistant")
    st.markdown(f"**Project:** {project['title']}")
    st.markdown("---")

    pool = get_research_pool(project["id"])
    confirmed = [p for p in pool if p.get("confirmed")]

    if not confirmed:
        st.warning("No confirmed papers in your research pool. Please complete the Analysis step first.")
        return

    gap = project.get("research_gap", "")
    if not gap:
        st.warning("No research gap set. Please complete the Analysis step first.")
        return

    # Style selector
    st.markdown("### Writing Style")
    style_label = st.radio(
        "Choose tone for AI writing:",
        list(STYLE_OPTIONS.keys()),
        horizontal=True,
        help="This applies to all sections."
    )
    style_key = STYLE_OPTIONS[style_label]
    st.caption(f"ℹ️ {STYLE_DESC[style_label]}")
    st.markdown("---")

    # Load existing drafts
    drafts = get_drafts(project["id"])

    # Section tabs
    tabs = st.tabs([title for _, title in SECTIONS])

    for tab, (section_key, section_title) in zip(tabs, SECTIONS):
        with tab:
            existing = drafts.get(section_key, "")

            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**Sources used:** {len(confirmed)} papers from research pool")
                st.markdown(f"**In-text citations:** Auto-inserted as (Author et al., Year)")
            with col2:
                generate_label = "🔄 Regenerate" if existing else "🤖 Generate"
                generate = st.button(
                    generate_label,
                    key=f"gen_{section_key}",
                    use_container_width=True,
                    type="primary"
                )

            if generate:
                with st.spinner(f"Writing {section_title}... (this may take 15–30 seconds)"):
                    content = write_section(
                        section=section_key,
                        topic=project["topic"],
                        objective=project["objective"],
                        gap=gap,
                        papers=confirmed,
                        style_preset=style_key,
                    )
                save_draft(project["id"], section_key, content, style_key)
                drafts[section_key] = content
                st.rerun()

            if existing or drafts.get(section_key):
                content_to_show = drafts.get(section_key, existing)

                # Editable text area
                edited = st.text_area(
                    "Edit content:",
                    value=content_to_show,
                    height=400,
                    key=f"edit_{section_key}",
                    label_visibility="collapsed"
                )

                col1, col2 = st.columns([1, 3])
                with col1:
                    if st.button("💾 Save edits", key=f"save_{section_key}", use_container_width=True):
                        save_draft(project["id"], section_key, edited, style_key)
                        st.success("Saved!")

                # Citation preview
                with st.expander("📚 Citations used in this section"):
                    import re
                    found = re.findall(r"\([A-Za-z]+(?:\s+et\s+al\.)?,\s*\d{4}\)", content_to_show)
                    found += re.findall(r"\([A-Za-z]+\s+&\s+[A-Za-z]+,\s*\d{4}\)", content_to_show)
                    if found:
                        for c in sorted(set(found)):
                            st.markdown(f"- {c}")
                    else:
                        st.caption("No citations detected yet — generate content first.")
            else:
                st.info(f"Click **Generate** to write the {section_title} section using your research pool.")

    st.markdown("---")

    # Check if all sections done
    all_done = all(drafts.get(k) for k, _ in SECTIONS)
    done_count = sum(1 for k, _ in SECTIONS if drafts.get(k))

    st.markdown(f"**Progress:** {done_count}/{len(SECTIONS)} sections written")

    if all_done:
        st.success("✅ All sections complete! Ready to export.")
        if st.button("Proceed to Export →", type="primary", use_container_width=True):
            update_project_status(project["id"], "done")
            st.session_state["current_project"]["status"] = "done"
            st.rerun()
    else:
        remaining = [title for key, title in SECTIONS if not drafts.get(key)]
        st.info(f"Remaining: {', '.join(remaining)}")
