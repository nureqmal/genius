import streamlit as st
from utils.auth import require_auth
from utils.search import search_all_sources, CURRENT_YEAR, RECENT_YEARS
from utils.db import save_paper_to_pool, get_research_pool, update_project_status

SOURCE_COLORS = {
    "Semantic Scholar": "badge-blue",
    "arXiv": "badge-amber",
    "PubMed": "badge-green",
    "CrossRef": "badge-gray",
}


def show():
    require_auth()
    project = st.session_state.get("current_project")
    if not project:
        st.warning("No active project. Please create or open a project first.")
        return

    st.markdown(f"## 🔍 Paper Search")
    st.markdown(f"**Project:** {project['title']}")
    st.markdown("---")

    pool = get_research_pool(project["id"])
    if pool:
        st.success(f"✅ {len(pool)} paper(s) in your research pool.")
        if st.button("Proceed to Analysis →", type="primary"):
            update_project_status(project["id"], "analysing")
            st.session_state["current_project"]["status"] = "analysing"
            st.session_state["current_page"] = "🧠 Analyse"
            st.rerun()
        st.markdown("---")

    st.info("🤖 AI will generate targeted search queries based on your topic, objective, and research gap.")

    search_clicked = st.button("🔍 Search Papers", use_container_width=True, type="primary")

    with st.expander("ℹ️ Source Date Intelligence"):
        st.markdown(f"""
| Source Type | Rule |
|---|---|
| **Conceptual / foundational** | Any year — ranked by citation count + relevancy |
| **Methods / Results** | ≤ {RECENT_YEARS} years (since {CURRENT_YEAR - RECENT_YEARS}) |
| **Exception** | Older papers with 500+ citations included with a flag |
        """)

    if search_clicked:
        with st.spinner("🤖 Gemini is generating targeted queries and searching 4 databases..."):
            results = search_all_sources(
                project["topic"],
                project["objective"],
                project.get("research_gap", "")
            )
        st.session_state["search_results"] = results

    results = st.session_state.get("search_results", [])
    if not results:
        if search_clicked:
            st.warning("No results found. Try refining your topic or objective.")
        return

    st.markdown(f"**{len(results)} relevant papers found** — select the ones you want:")
    st.markdown("<br>", unsafe_allow_html=True)

    pool_titles = {p["paper_title"].lower().strip()[:60] for p in pool}

    for i, paper in enumerate(results):
        title_key = paper["title"].lower().strip()[:60]
        already_added = title_key in pool_titles
        with st.container():
            col1, col2 = st.columns([5, 1])
            with col1:
                exception_flag = " 🏛️ *Classic exception*" if paper.get("is_exception") else ""
                st.markdown(f"**{paper['title']}**{exception_flag}")
                badge_cls = SOURCE_COLORS.get(paper["source"], "badge-gray")
                relevancy_pct = paper.get("relevancy_pct", 0)
                st.markdown(
                    f'<span class="badge {badge_cls}">{paper["source"]}</span> '
                    f'<span class="badge badge-gray">📅 {paper.get("year") or "n.d."}</span> '
                    f'<span class="badge badge-blue">⭐ {paper["citation_count"]} citations</span> '
                    f'<span class="badge badge-green">🎯 {relevancy_pct}% relevant</span>',
                    unsafe_allow_html=True
                )
                if paper.get("venue"):
                    st.caption(f"📰 {paper['venue']}")
                if paper.get("abstract"):
                    with st.expander("Abstract"):
                        st.write(paper["abstract"][:600])
                if paper.get("pdf_url"):
                    st.markdown(f"[🔗 View paper]({paper['pdf_url']})")
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if already_added:
                    st.markdown('<span class="badge badge-green">✓ Added</span>', unsafe_allow_html=True)
                else:
                    if st.button("+ Add", key=f"add_{i}", use_container_width=True):
                        saved = save_paper_to_pool(project["id"], paper)
                        if saved:
                            pool_titles.add(title_key)
                            st.rerun()
            st.markdown("---")
