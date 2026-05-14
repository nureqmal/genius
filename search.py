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

    # Current pool summary
    pool = get_research_pool(project["id"])
    if pool:
        st.success(f"✅ {len(pool)} paper(s) in your research pool.")
        if st.button("Proceed to Analysis →", type="primary"):
            update_project_status(project["id"], "analysing")
            st.session_state["current_project"]["status"] = "analysing"
            st.rerun()
        st.markdown("---")

    # Search controls
    col1, col2 = st.columns([3, 1])
    with col1:
        custom_query = st.text_input(
            "Search query",
            value=project["topic"],
            help="Modify to narrow or broaden the search"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        search_clicked = st.button("🔍 Search", use_container_width=True, type="primary")

    # Date intelligence info
    with st.expander("ℹ️ Source Date Intelligence — how papers are filtered"):
        st.markdown(f"""
The platform automatically applies academic sourcing standards:

| Source Type | Rule |
|---|---|
| **Conceptual / foundational** | Any year — ranked by citation count + relevancy |
| **Methods / Results** | ≤ {RECENT_YEARS} years (since {CURRENT_YEAR - RECENT_YEARS}) preferred |
| **Exception** | Older papers with 500+ citations included with a flag |

Papers that don't meet the date criteria for methods/results are excluded from results automatically.
        """)

    # Run search
    if search_clicked or "search_results" not in st.session_state:
        if search_clicked:
            with st.spinner("Searching Semantic Scholar, arXiv, PubMed, CrossRef..."):
                results = search_all_sources(custom_query, project["objective"])
            st.session_state["search_results"] = results

    results = st.session_state.get("search_results", [])

    if not results:
        if search_clicked:
            st.warning("No results found. Try a different search query.")
        return

    st.markdown(f"**{len(results)} papers found** — select the ones relevant to your research:")
    st.markdown("<br>", unsafe_allow_html=True)

    # Track which papers are already in pool
    pool_titles = {p["paper_title"].lower().strip()[:60] for p in pool}

    added_count = 0
    for i, paper in enumerate(results):
        title_key = paper["title"].lower().strip()[:60]
        already_added = title_key in pool_titles

        with st.container():
            col1, col2 = st.columns([5, 1])
            with col1:
                # Title + badges
                exception_flag = " 🏛️ *Classic exception*" if paper.get("is_exception") else ""
                st.markdown(f"**{paper['title']}**{exception_flag}")

                badge_cls = SOURCE_COLORS.get(paper["source"], "badge-gray")
                relevancy_pct = int(paper["relevancy_score"] * 100)
                year_display = paper.get("year") or "n.d."

                st.markdown(
                    f'<span class="badge {badge_cls}">{paper["source"]}</span> '
                    f'<span class="badge badge-gray">📅 {year_display}</span> '
                    f'<span class="badge badge-blue">⭐ {paper["citation_count"]} citations</span> '
                    f'<span class="badge badge-green">🎯 {relevancy_pct}% relevant</span>',
                    unsafe_allow_html=True
                )

                if paper.get("abstract"):
                    with st.expander("Abstract"):
                        st.write(paper["abstract"][:600] + ("..." if len(paper.get("abstract", "")) > 600 else ""))

                if paper.get("pdf_url"):
                    st.markdown(f"[🔗 View paper]({paper['pdf_url']})")

            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if already_added:
                    st.markdown('<span class="badge badge-green">✓ Added</span>', unsafe_allow_html=True)
                else:
                    if st.button("+ Add", key=f"add_{i}", use_container_width=True):
                        with st.spinner("Adding..."):
                            saved = save_paper_to_pool(project["id"], paper)
                        if saved:
                            pool_titles.add(title_key)
                            added_count += 1
                            st.success("Added!")
                            st.rerun()

            st.markdown("---")

    if added_count:
        st.rerun()
