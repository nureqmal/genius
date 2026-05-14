from utils.auth import get_supabase
import streamlit as st


def create_project(user_id, topic, objective, gap=""):
    sb = get_supabase()
    title = topic[:80] + ("..." if len(topic) > 80 else "")
    try:
        res = sb.table("projects").insert({
            "user_id": user_id, "title": title, "topic": topic,
            "objective": objective, "research_gap": gap, "status": "searching"
        }).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        st.error(f"Failed to create project: {e}")
        return None


def get_user_projects(user_id):
    sb = get_supabase()
    try:
        res = sb.table("projects").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
        return res.data or []
    except Exception:
        return []


def get_project(project_id):
    sb = get_supabase()
    try:
        res = sb.table("projects").select("*").eq("id", project_id).single().execute()
        return res.data
    except Exception:
        return None


def update_project_status(project_id, status):
    sb = get_supabase()
    try:
        sb.table("projects").update({"status": status}).eq("id", project_id).execute()
    except Exception:
        pass


def update_project_gap(project_id, gap):
    sb = get_supabase()
    try:
        sb.table("projects").update({"research_gap": gap}).eq("id", project_id).execute()
    except Exception:
        pass


def save_paper_to_pool(project_id, paper):
    sb = get_supabase()
    try:
        res = sb.table("research_pool").insert({
            "project_id": project_id,
            "paper_title": paper.get("title", ""),
            "authors": paper.get("authors", ""),
            "year": paper.get("year"),
            "doi": paper.get("doi", ""),
            "abstract": paper.get("abstract", ""),
            "source": paper.get("source", ""),
            "citation_count": paper.get("citation_count", 0),
            "relevancy_score": paper.get("relevancy_score", 0),
            "source_type": paper.get("source_type", ""),
            "is_exception": paper.get("is_exception", False),
            "confirmed": False,
        }).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None


def get_research_pool(project_id):
    sb = get_supabase()
    try:
        res = sb.table("research_pool").select("*").eq("project_id", project_id).order("relevancy_score", desc=True).execute()
        return res.data or []
    except Exception:
        return []


def confirm_paper(pool_id, summary, findings, methodology):
    sb = get_supabase()
    try:
        sb.table("research_pool").update({
            "extracted_summary": summary,
            "extracted_findings": findings,
            "extracted_methodology": methodology,
            "confirmed": True,
        }).eq("id", pool_id).execute()
    except Exception:
        pass


def remove_paper_from_pool(pool_id):
    sb = get_supabase()
    try:
        sb.table("research_pool").delete().eq("id", pool_id).execute()
    except Exception:
        pass


def save_draft(project_id, section, content, style):
    sb = get_supabase()
    try:
        existing = sb.table("drafts").select("id").eq("project_id", project_id).eq("section", section).execute()
        if existing.data:
            sb.table("drafts").update({"content": content, "style_preset": style}).eq(
                "project_id", project_id).eq("section", section).execute()
        else:
            sb.table("drafts").insert({
                "project_id": project_id, "section": section,
                "content": content, "style_preset": style,
            }).execute()
    except Exception:
        pass


def get_drafts(project_id):
    sb = get_supabase()
    try:
        res = sb.table("drafts").select("*").eq("project_id", project_id).execute()
        return {d["section"]: d["content"] for d in (res.data or [])}
    except Exception:
        return {}


def save_citations(project_id, papers):
    from utils.citations import format_apa, format_ieee, format_mla, fetch_doi_metadata
    sb = get_supabase()
    for p in papers:
        meta = fetch_doi_metadata(p.get("doi", "")) if p.get("doi") else {}
        try:
            sb.table("citations").upsert({
                "project_id": project_id,
                "pool_id": p.get("id"),
                "author_last": (p.get("authors", "Unknown").split(",")[0].split()[-1]),
                "year": p.get("year"),
                "doi": p.get("doi", ""),
                "full_title": p.get("paper_title") or p.get("title", ""),
                "format_apa": format_apa(p, meta),
                "format_ieee": format_ieee(p, meta),
                "format_mla": format_mla(p, meta),
            }).execute()
        except Exception:
            pass
