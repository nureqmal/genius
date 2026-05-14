import streamlit as st
from utils.auth import require_auth
from utils.ai import analyse_paper, detect_research_gap, detect_contradictions
from utils.db import (get_research_pool, confirm_paper, remove_paper_from_pool,
                      update_project_status, update_project_gap, get_project, save_citations)


def show():
    require_auth()

    project = st.session_state.get("current_project")
    if not project:
        st.warning("No active project.")
        return

    # Refresh project from DB for latest gap
    project = get_project(project["id"]) or project
    st.session_state["current_project"] = project

    st.markdown("## 🧠 Analysis")
    st.markdown(f"**Project:** {project['title']}")
    st.markdown("---")

    pool = get_research_pool(project["id"])
    if not pool:
        st.warning("No papers in your research pool. Please search and add papers first.")
        return

    confirmed = [p for p in pool if p.get("confirmed")]
    unconfirmed = [p for p in pool if not p.get("confirmed")]

    # ── Step 1: Extract from papers ──
    st.markdown("### Step 1 — Extract from Papers")
    st.markdown(f"{len(pool)} papers total · {len(confirmed)} confirmed · {len(unconfirmed)} pending")

    if unconfirmed:
        if st.button(f"🤖 Extract from all {len(unconfirmed)} pending papers", type="primary"):
            progress = st.progress(0)
            for idx, paper in enumerate(unconfirmed):
                with st.spinner(f"Analysing: {paper['paper_title'][:60]}..."):
                    result = analyse_paper({
                        "title": paper["paper_title"],
                        "authors": paper.get("authors", ""),
                        "year": paper.get("year"),
                        "abstract": paper.get("abstract", ""),
                    })
                confirm_paper(
                    paper["id"],
                    result.get("summary", ""),
                    result.get("key_findings", ""),
                    result.get("methodology", ""),
                )
                progress.progress((idx + 1) / len(unconfirmed))
            st.success("Extraction complete!")
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Validation Checkpoint ──
    st.markdown("### Step 2 — Validation Checkpoint")
    st.markdown("Review and edit extracted findings. Remove any irrelevant papers.")

    pool = get_research_pool(project["id"])  # refresh
    for paper in pool:
        with st.expander(f"📄 {paper['paper_title'][:80]} ({paper.get('year', '?')})"):
            col1, col2 = st.columns([5, 1])
            with col1:
                exception_note = " 🏛️ Classic exception (high citation, older paper)" if paper.get("is_exception") else ""
                st.caption(f"{paper.get('source', '')} · {paper.get('citation_count', 0)} citations · "
                           f"{int((paper.get('relevancy_score') or 0) * 100)}% relevant{exception_note}")

                summary = st.text_area(
                    "Summary", value=paper.get("extracted_summary", ""),
                    key=f"sum_{paper['id']}", height=80
                )
                findings = st.text_area(
                    "Key Findings", value=paper.get("extracted_findings", ""),
                    key=f"find_{paper['id']}", height=80
                )
                methodology = st.text_area(
                    "Methodology", value=paper.get("extracted_methodology", ""),
                    key=f"meth_{paper['id']}", height=60
                )

                btn1, btn2 = st.columns(2)
                with btn1:
                    if st.button("✅ Confirm", key=f"conf_{paper['id']}", use_container_width=True):
                        confirm_paper(paper["id"], summary, findings, methodology)
                        st.success("Confirmed!")
                        st.rerun()
                with btn2:
                    if st.button("🗑️ Remove", key=f"rem_{paper['id']}", use_container_width=True):
                        remove_paper_from_pool(paper["id"])
                        st.rerun()
            with col2:
                if paper.get("confirmed"):
                    st.markdown('<span class="badge badge-green">✓ Confirmed</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="badge badge-amber">⏳ Pending</span>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Step 3: Research Gap ──
    pool = get_research_pool(project["id"])
    confirmed = [p for p in pool if p.get("confirmed")]

    st.markdown("### Step 3 — Research Gap")
    current_gap = project.get("research_gap", "")

    if current_gap:
        st.markdown("**Current gap statement:**")
        st.markdown(f'<div class="section-box">{current_gap}</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if confirmed and st.button(
            "🔍 Detect / Validate Gap with AI" if current_gap else "🔍 Auto-detect Gap",
            use_container_width=True, type="primary"
        ):
            with st.spinner("Analysing literature for research gap..."):
                gap = detect_research_gap(
                    project["topic"],
                    project["objective"],
                    confirmed,
                    current_gap
                )
            update_project_gap(project["id"], gap)
            st.session_state["current_project"]["research_gap"] = gap
            st.success("Research gap updated!")
            st.rerun()

    with col2:
        manual_gap = st.text_area(
            "Or write your own gap statement:",
            value=current_gap, height=100, key="manual_gap"
        )
        if st.button("Save Gap", use_container_width=True):
            update_project_gap(project["id"], manual_gap)
            st.success("Saved!")
            st.rerun()

    st.markdown("---")

    # ── Step 4: Contradiction Check (nice-to-have) ──
    if confirmed and len(confirmed) >= 2:
        st.markdown("### Step 4 — Contradiction Check *(optional)*")
        if st.button("🔎 Check for Contradictions"):
            with st.spinner("Scanning for contradictions..."):
                contradictions = detect_contradictions(confirmed)
            if contradictions:
                st.warning("⚠️ Potential contradictions found:")
                for c in contradictions:
                    st.markdown(f"- {c}")
            else:
                st.success("No contradictions detected.")

    st.markdown("---")

    # ── Proceed ──
    all_confirmed = all(p.get("confirmed") for p in pool)
    has_gap = bool(project.get("research_gap", "").strip())

    if all_confirmed and has_gap:
        st.success("✅ All papers confirmed and research gap set. Ready to write!")
        if st.button("Proceed to Writing →", type="primary", use_container_width=True):
            save_citations(project["id"], pool)
            update_project_status(project["id"], "writing")
            st.session_state["current_project"]["status"] = "writing"
            st.rerun()
    else:
        missing = []
        if not all_confirmed:
            missing.append("confirm all papers")
        if not has_gap:
            missing.append("set a research gap")
        st.info(f"To proceed: {' and '.join(missing)}.")
