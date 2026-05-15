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


def generate_search_queries(topic: str, objective: str, gap: str = "") -> list:
    prompt = f"""You are an expert academic research librarian specialising in finding highly specific academic papers.

A researcher needs papers for this project:

TOPIC: {topic}
OBJECTIVE: {objective}
RESEARCH GAP: {gap or "Not specified"}

Your job: Generate 6 highly specific search queries to find the MOST RELEVANT academic papers.

Rules:
- Each query must be 3-7 words
- Be VERY specific — include specific methods, substances, tools, techniques mentioned
- Cover different angles: (1) core method, (2) application domain, (3) specific technique, (4) comparison/review, (5) recent advances, (6) specific materials/subjects
- Use exact academic terminology
- Do NOT generate generic queries
- Queries must be diverse — no repetition of same concept

Example for "Lipid Profiling using GCMS and Machine Learning for Halal Authentication":
["GC-MS fatty acid halal authentication", "lipid profiling lard adulteration detection", "machine learning food fraud classification", "chemometrics edible oil authentication", "FAME analysis halal food verification", "SVM PCA oil adulteration classification"]

Return ONLY a JSON array of 6 strings. No explanation."""

    try:
        response = model.generate_content(prompt)
        raw = re.sub(r"```json|```", "", response.text.strip()).strip()
        queries = json.loads(raw)
        if isinstance(queries, list) and len(queries) >= 3:
            return [q.strip() for q in queries if isinstance(q, str)][:6]
    except Exception:
        pass

    # Fallback
    words = [w for w in (topic + " " + objective).split()
             if len(w) > 4 and w.lower() not in
             {"using","based","approach","study","research","analysis","towards","within","their","which"}]
    return [" ".join(words[i:i+4]) for i in range(0, min(len(words), 16), 4) if words[i:i+4]]


def classify_source_type(topic: str, objective: str) -> str:
    method_keywords = [
        "method", "methodology", "approach", "technique", "algorithm", "model",
        "framework", "result", "finding", "analysis", "experiment", "performance",
        "accuracy", "detection", "classification", "gcms", "gc-ms", "ml",
        "machine learning", "deep learning", "neural", "profiling", "chromatography"
    ]
    combined = (topic + " " + objective).lower()
    hits = sum(1 for kw in method_keywords if kw in combined)
    return "method_result" if hits >= 2 else "conceptual"


def is_recent_enough(year: int, source_type: str, citation_count: int):
    if source_type == "conceptual" or not year:
        return True, False
    age = CURRENT_YEAR - year
    if age <= RECENT_YEARS:
        return True, False
    if citation_count >= HIGH_CITATION_THRESHOLD:
        return True, True
    return False, False


def gemini_score_papers(papers: list, topic: str, objective: str, gap: str = "") -> list:
    if not papers:
        return papers

    paper_list = "\n".join([
        f"{i+1}. Title: {p['title']}\n   Abstract: {(p.get('abstract') or 'No abstract')[:250]}"
        for i, p in enumerate(papers[:25])
    ])

    prompt = f"""You are a strict academic research evaluator.

Research Topic: {topic}
Research Objective: {objective}
Research Gap: {gap or "Not specified"}

Score each paper's relevance from 0-100:
- 85-100: Directly relevant — same method, same domain, same materials
- 60-84: Relevant — same domain OR same method but different application
- 30-59: Partially relevant — related field, could be useful as background
- 0-29: NOT relevant — different domain, coincidental keyword match only

IMPORTANT: Be STRICT. A paper about "halal tourism sentiment analysis" is 0 for a lipid profiling study.
Only score high if the paper genuinely helps the research.

Papers to score:
{paper_list}

Return ONLY a JSON array of {min(len(papers), 25)} integer scores. Example: [92, 45, 78, 12, 0]"""

    try:
        response = model.generate_content(prompt)
        raw = re.sub(r"```json|```", "", response.text.strip()).strip()
        scores = json.loads(raw)
        if isinstance(scores, list):
            for i, score in enumerate(scores[:len(papers)]):
                papers[i]["relevancy_pct"] = max(0, min(100, int(score)))
                papers[i]["relevancy_score"] = round(papers[i]["relevancy_pct"] / 100, 2)
    except Exception:
        for p in papers:
            p.setdefault("relevancy_pct", 40)
            p.setdefault("relevancy_score", 0.4)

    return papers


def search_semantic_scholar(query: str, source_type: str, limit: int = 8) -> list:
    try:
        res = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": query, "limit": limit,
                    "fields": "title,authors,year,abstract,citationCount,externalIds,publicationVenue"},
            timeout=10
        )
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
        results.append({
            "title": p.get("title", ""),
            "authors": ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3]),
            "year": year, "abstract": p.get("abstract", ""), "doi": doi,
            "venue": (p.get("publicationVenue") or {}).get("name", ""),
            "source": "Semantic Scholar", "citation_count": citations,
            "relevancy_score": 0.5, "relevancy_pct": 50,
            "source_type": source_type, "is_exception": is_exc,
            "pdf_url": f"https://doi.org/{doi}" if doi else "",
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
        year_str = p.get("pubdate", "")[:4]
        year = int(year_str) if year_str.isdigit() else 0
        doi = next((i.get("value", "") for i in (p.get("articleids") or [])
                    if i.get("idtype") == "doi"), "")
        passes, is_exc = is_recent_enough(year, source_type, 0)
        if not passes:
            continue
        results.append({
            "title": p.get("title", ""),
            "authors": ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3]),
            "year": year, "abstract": "", "doi": doi,
            "venue": p.get("source", ""), "source": "PubMed", "citation_count": 0,
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
        citations = p.get("is-referenced-by-count", 0)
        doi = p.get("DOI", "")
        passes, is_exc = is_recent_enough(year, source_type, citations)
        if not passes:
            continue
        results.append({
            "title": title,
            "authors": ", ".join(
                f"{a.get('family', '')} {a.get('given', '')[:1]}"
                for a in (p.get("author") or [])[:3]
            ),
            "year": year, "abstract": p.get("abstract", ""), "doi": doi,
            "venue": (p.get("container-title") or [""])[0],
            "source": "CrossRef", "citation_count": citations,
            "relevancy_score": 0.5, "relevancy_pct": 50,
            "source_type": source_type, "is_exception": is_exc,
            "pdf_url": f"https://doi.org/{doi}" if doi else "",
        })
    return results


def search_arxiv(query: str, source_type: str, limit: int = 4) -> list:
    try:
        res = requests.get(
            "http://export.arxiv.org/api/query",
            params={"search_query": f"all:{query}", "start": 0,
                    "max_results": limit, "sortBy": "relevance"}, timeout=10
        )
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
        arxiv_id = (e.findtext("atom:id", "", ns) or "").split("/abs/")[-1]
        passes, is_exc = is_recent_enough(year, source_type, 0)
        if not passes:
            continue
        results.append({
            "title": title,
            "authors": ", ".join(
                a.text for a in e.findall("atom:author/atom:name", ns)[:3] if a.text
            ),
            "year": year, "abstract": abstract, "doi": arxiv_id, "venue": "arXiv",
            "source": "arXiv", "citation_count": 0,
            "relevancy_score": 0.5, "relevancy_pct": 50,
            "source_type": source_type, "is_exception": is_exc,
            "pdf_url": f"https://arxiv.org/abs/{arxiv_id}",
        })
    return results


# ─────────────────────────────────────────────
# MASTER SEARCH
# ─────────────────────────────────────────────

def search_all_sources(topic: str, objective: str, gap: str = "") -> list:

    # Step 1: Gemini generates specific queries
    queries = generate_search_queries(topic, objective, gap)
    source_type = classify_source_type(topic, objective)

    # Step 2: Search all sources
    all_results = []
    seen_titles = set()

    for query in queries:
        batch = []
        batch += search_semantic_scholar(query, source_type, limit=5)
        batch += search_pubmed(query, source_type, limit=4)
        batch += search_crossref(query, source_type, limit=4)
        batch += search_arxiv(query, source_type, limit=3)

        for r in batch:
            key = r["title"].lower().strip()[:70]
            if key and key not in seen_titles and len(r["title"]) > 10:
                seen_titles.add(key)
                all_results.append(r)

        time.sleep(0.4)

    if not all_results:
        return []

    # Step 3: Gemini scores relevancy — STRICT mode
    scored = gemini_score_papers(all_results, topic, objective, gap)

    # Step 4: Sort by relevancy first, citations second
    scored.sort(
        key=lambda x: (x.get("relevancy_pct", 0), x.get("citation_count", 0)),
        reverse=True
    )

    # Step 5: Keep only relevant papers (>=40%), minimum 8 results
    relevant = [p for p in scored if p.get("relevancy_pct", 0) >= 40]
    if len(relevant) < 8:
        relevant = scored[:15]  # fallback — top 15 regardless

    return relevant[:25]
