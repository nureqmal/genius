import requests
import time
from datetime import datetime
import google.generativeai as genai
import streamlit as st
import json
import re
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _get_secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, "")


genai.configure(api_key=_get_secret("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

CURRENT_YEAR = datetime.now().year
RECENT_YEARS = 5
HIGH_CITATION_THRESHOLD = 500


# ─────────────────────────────────────────────
# STEP 1: Gemini extracts smart search queries
# ─────────────────────────────────────────────

def generate_search_queries(topic: str, objective: str) -> list:
    prompt = f"""You are an expert academic research librarian.

Given this research topic and objective, generate exactly 4 targeted search queries to find the most relevant academic papers.

Topic: {topic}
Objective: {objective}

Rules:
- Each query must be SHORT (3-6 words max)
- Focus on CORE concepts only
- Queries must be diverse — cover different angles
- Use terms that appear in academic paper titles/abstracts
- No boolean operators, no quotes

Return ONLY a JSON array of 4 strings. Example:
["query one", "query two", "query three", "query four"]"""

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        queries = json.loads(raw)
        if isinstance(queries, list):
            return [q for q in queries if isinstance(q, str)][:4]
    except Exception:
        pass

    # Fallback: extract keywords manually
    words = (topic + " " + objective).split()
    stopwords = {"a","an","the","and","or","for","of","in","to","with","using",
                 "based","on","is","are","was","be","this","that","approach",
                 "study","research","analysis","using","towards","via"}
    keywords = [w for w in words if w.lower() not in stopwords and len(w) > 3][:8]
    mid = len(keywords) // 2
    return [" ".join(keywords[:4]), " ".join(keywords[4:8]),
            " ".join(keywords[:3]), " ".join(keywords[2:6])]


# ─────────────────────────────────────────────
# STEP 2: Source date intelligence
# ─────────────────────────────────────────────

def classify_source_type(topic: str, objective: str) -> str:
    method_keywords = [
        "method", "methodology", "approach", "technique", "algorithm",
        "model", "framework", "result", "finding", "analysis", "experiment",
        "performance", "accuracy", "detection", "classification", "using",
        "gcms", "gc-ms", "ml", "machine learning", "deep learning", "neural"
    ]
    combined = (topic + " " + objective).lower()
    hits = sum(1 for kw in method_keywords if kw in combined)
    return "method_result" if hits >= 2 else "conceptual"


def is_recent_enough(year: int, source_type: str, citation_count: int):
    if source_type == "conceptual" or year is None:
        return True, False
    age = CURRENT_YEAR - year
    if age <= RECENT_YEARS:
        return True, False
    if citation_count >= HIGH_CITATION_THRESHOLD:
        return True, True
    return False, False


# ─────────────────────────────────────────────
# STEP 3: Gemini scores relevancy properly
# ─────────────────────────────────────────────

def gemini_score_papers(papers: list, topic: str, objective: str) -> list:
    if not papers:
        return papers

    # Build paper list for Gemini
    paper_list = "\n".join([
        f"{i+1}. Title: {p['title']}\n   Abstract: {(p.get('abstract') or '')[:200]}"
        for i, p in enumerate(papers[:20])
    ])

    prompt = f"""You are an expert academic research assistant.

Research Topic: {topic}
Research Objective: {objective}

Rate each paper's relevance to the topic and objective above.
Score from 0 to 100 where:
- 80-100: Highly relevant, directly addresses the topic
- 50-79: Moderately relevant, related field or method
- 20-49: Loosely related
- 0-19: Not relevant

Papers:
{paper_list}

Return ONLY a JSON array of scores in order. Example for 5 papers: [85, 62, 90, 45, 78]
Return exactly {min(len(papers), 20)} scores."""

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        scores = json.loads(raw)
        if isinstance(scores, list):
            for i, score in enumerate(scores[:len(papers)]):
                papers[i]["relevancy_score"] = round(int(score) / 100, 2)
                papers[i]["relevancy_pct"] = int(score)
    except Exception:
        # Fallback to keyword scoring
        for p in papers:
            keywords = set((topic + " " + objective).lower().split())
            text = (p.get("title", "") + " " + p.get("abstract", "")).lower()
            hits = sum(1 for kw in keywords if len(kw) > 3 and kw in text)
            score = min(int((hits / max(len(keywords), 1)) * 100), 100)
            p["relevancy_score"] = round(score / 100, 2)
            p["relevancy_pct"] = score

    return papers


# ─────────────────────────────────────────────
# STEP 4: Search each source
# ─────────────────────────────────────────────

def search_semantic_scholar(query: str, source_type: str, limit: int = 8) -> list:
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,abstract,citationCount,externalIds,publicationVenue"
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json().get("data", [])
    except Exception:
        return []

    results = []
    for p in data:
        year = p.get("year") or 0
        citations = p.get("citationCount") or 0
        passes, is_exc = is_recent_enough(year, source_type, citations)
        if not passes:
            continue
        doi = (p.get("externalIds") or {}).get("DOI", "")
        venue = (p.get("publicationVenue") or {}).get("name", "")
        results.append({
            "title": p.get("title", ""),
            "authors": ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3]),
            "year": year,
            "abstract": p.get("abstract", ""),
            "doi": doi,
            "venue": venue,
            "source": "Semantic Scholar",
            "citation_count": citations,
            "relevancy_score": 0.5,
            "relevancy_pct": 50,
            "source_type": source_type,
            "is_exception": is_exc,
            "pdf_url": f"https://doi.org/{doi}" if doi else "",
        })
    return results


def search_arxiv(query: str, source_type: str, limit: int = 6) -> list:
    url = "http://export.arxiv.org/api/query"
    params = {"search_query": f"all:{query}", "start": 0,
              "max_results": limit, "sortBy": "relevance"}
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
    except Exception:
        return []

    import xml.etree.ElementTree as ET
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(res.text)
    results = []
    for e in root.findall("atom:entry", ns):
        title = (e.findtext("atom:title", "", ns) or "").strip().replace("\n", " ")
        abstract = (e.findtext("atom:summary", "", ns) or "").strip().replace("\n", " ")
        published = e.findtext("atom:published", "", ns) or ""
        year = int(published[:4]) if published else 0
        authors = ", ".join(
            a.text for a in e.findall("atom:author/atom:name", ns)[:3] if a.text
        )
        arxiv_id = (e.findtext("atom:id", "", ns) or "").split("/abs/")[-1]
        passes, is_exc = is_recent_enough(year, source_type, 0)
        if not passes:
            continue
        results.append({
            "title": title, "authors": authors, "year": year,
            "abstract": abstract, "doi": arxiv_id, "venue": "arXiv",
            "source": "arXiv", "citation_count": 0,
            "relevancy_score": 0.5, "relevancy_pct": 50,
            "source_type": source_type, "is_exception": is_exc,
            "pdf_url": f"https://arxiv.org/abs/{arxiv_id}",
        })
    return results


def search_pubmed(query: str, source_type: str, limit: int = 6) -> list:
    try:
        res = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmax": limit,
                    "retmode": "json", "sort": "relevance"}, timeout=10
        )
        ids = res.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        time.sleep(0.3)
        res2 = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"}, timeout=10
        )
        summaries = res2.json().get("result", {})
    except Exception:
        return []

    results = []
    for uid in ids:
        p = summaries.get(uid, {})
        if not p or uid == "uids":
            continue
        title = p.get("title", "")
        year_str = p.get("pubdate", "")[:4]
        year = int(year_str) if year_str.isdigit() else 0
        authors = ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3])
        doi = next((i.get("value", "") for i in (p.get("articleids") or [])
                    if i.get("idtype") == "doi"), "")
        journal = p.get("source", "")
        passes, is_exc = is_recent_enough(year, source_type, 0)
        if not passes:
            continue
        results.append({
            "title": title, "authors": authors, "year": year,
            "abstract": "", "doi": doi, "venue": journal,
            "source": "PubMed", "citation_count": 0,
            "relevancy_score": 0.5, "relevancy_pct": 50,
            "source_type": source_type, "is_exception": is_exc,
            "pdf_url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
        })
    return results


def search_crossref(query: str, source_type: str, limit: int = 6) -> list:
    try:
        res = requests.get(
            "https://api.crossref.org/works",
            params={"query": query, "rows": limit,
                    "select": "title,author,published,DOI,abstract,is-referenced-by-count,container-title"},
            timeout=10, headers={"User-Agent": "ResearchAI/1.0"}
        )
        items = res.json().get("message", {}).get("items", [])
    except Exception:
        return []

    results = []
    for p in items:
        title = (p.get("title") or [""])[0]
        if not title:
            continue
        pub = p.get("published", {}).get("date-parts", [[0]])[0]
        year = pub[0] if pub else 0
        authors_raw = p.get("author") or []
        authors = ", ".join(
            f"{a.get('family', '')} {a.get('given', '')[:1]}" for a in authors_raw[:3]
        )
        doi = p.get("DOI", "")
        citations = p.get("is-referenced-by-count", 0)
        journal = (p.get("container-title") or [""])[0]
        abstract = p.get("abstract", "")
        passes, is_exc = is_recent_enough(year, source_type, citations)
        if not passes:
            continue
        results.append({
            "title": title, "authors": authors, "year": year,
            "abstract": abstract, "doi": doi, "venue": journal,
            "source": "CrossRef", "citation_count": citations,
            "relevancy_score": 0.5, "relevancy_pct": 50,
            "source_type": source_type, "is_exception": is_exc,
            "pdf_url": f"https://doi.org/{doi}" if doi else "",
        })
    return results


# ─────────────────────────────────────────────
# MASTER SEARCH
# ─────────────────────────────────────────────

def search_all_sources(topic: str, objective: str) -> list:

    # Step 1: Generate smart queries
    queries = generate_search_queries(topic, objective)
    source_type = classify_source_type(topic, objective)

    # Step 2: Search all sources with all queries
    all_results = []
    seen_titles = set()

    for query in queries:
        batch = []
        batch += search_semantic_scholar(query, source_type, limit=6)
        batch += search_pubmed(query, source_type, limit=4)
        batch += search_crossref(query, source_type, limit=4)
        batch += search_arxiv(query, source_type, limit=3)

        for r in batch:
            key = r["title"].lower().strip()[:70]
            if key and key not in seen_titles and len(r["title"]) > 10:
                seen_titles.add(key)
                all_results.append(r)

        time.sleep(0.5)

    # Step 3: Filter low quality — tapi jangan terlalu strict
    filtered = []
    for r in all_results:
        age = CURRENT_YEAR - (r.get("year") or CURRENT_YEAR)
        has_citations = r.get("citation_count", 0) > 0
        is_very_recent = age <= 3
        is_semantic = r.get("source") == "Semantic Scholar"
        if has_citations or is_very_recent or is_semantic:
            filtered.append(r)

    # Kalau filter terlalu strict, guna semua
    if len(filtered) < 5:
        filtered = all_results

    # Kalau still empty, return empty dengan message
    if not filtered:
        return []

    # Step 4: Gemini scores relevancy
    scored = gemini_score_papers(filtered, topic, objective)

    # Step 5: Sort dulu by relevancy + citation
    scored.sort(
        key=lambda x: (x.get("relevancy_pct", 0), x.get("citation_count", 0)),
        reverse=True
    )

    # Step 6: Filter below 30% TAPI pastikan ada at least 10 results
    relevant = [p for p in scored if p.get("relevancy_pct", 0) >= 30]
    if len(relevant) < 10:
        relevant = scored  # buang filter, bagi semua

    return relevant[:30]
