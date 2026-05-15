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
    prompt = f"""You are an expert academic research librarian.

A researcher needs academic papers for this project:

TOPIC: {topic}
OBJECTIVE: {objective}
RESEARCH GAP: {gap or "Not specified"}

Generate 6 highly specific search queries for Semantic Scholar and PubMed.

STRICT RULES:
- Each query: 3-6 words ONLY
- Use EXACT scientific/technical terms from the topic
- Be VERY specific — include specific methods, substances, instruments
- Cover 6 different angles of the research
- NO generic terms like "machine learning review" or "deep learning applications"
- Queries must match what appears in academic paper TITLES

Example for "Lipid Profiling GCMS Halal Authentication":
["GC-MS halal authentication fatty acid", "lipid profiling lard adulteration detection", "machine learning edible oil classification", "FAME chemometrics food authentication", "halal food verification chromatography", "SVM PCA oil adulteration"]

Return ONLY a JSON array of 6 strings. No explanation. No markdown."""

    try:
        response = model.generate_content(prompt)
        raw = re.sub(r"```json|```", "", response.text.strip()).strip()
        queries = json.loads(raw)
        if isinstance(queries, list) and len(queries) >= 3:
            return [q.strip() for q in queries if isinstance(q, str)][:6]
    except Exception:
        pass

    # Fallback — extract core keywords
    words = [w for w in (topic + " " + objective).split()
             if len(w) > 4 and w.lower() not in
             {"using", "based", "approach", "study", "research",
              "analysis", "towards", "within", "their", "which", "methods"}]
    queries = []
    for i in range(0, min(len(words), 20), 3):
        chunk = " ".join(words[i:i+4])
        if chunk:
            queries.append(chunk)
    return queries[:6]


def classify_source_type(topic: str, objective: str) -> str:
    method_keywords = [
        "method", "technique", "algorithm", "model", "result", "finding",
        "analysis", "experiment", "performance", "accuracy", "detection",
        "classification", "gcms", "gc-ms", "ml", "machine learning",
        "deep learning", "neural", "profiling", "chromatography", "spectroscopy"
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

Score each paper 0-100 for relevance:
- 85-100: Directly relevant — same method, domain, materials
- 60-84: Relevant — same domain OR same method, different application  
- 30-59: Partially relevant — related field, useful as background
- 0-29: NOT relevant — different domain, coincidental keyword match

BE STRICT:
- A finance paper is 0 for a food science study
- A tourism paper is 0 for a chemistry study
- Only score high if genuinely useful for THIS specific research

Papers:
{paper_list}

Return ONLY a JSON array of {min(len(papers), 25)} integer scores. Example: [92, 45, 0, 78]
No explanation. No markdown."""

    try:
        response = model.generate_content(prompt)
        raw = re.sub(r"```json|```", "", response.text.strip()).strip()
        scores = json.loads(raw)
        if isinstance(scores, list):
            for i, score in enumerate(scores[:len(papers)]):
                try:
                    papers[i]["relevancy_pct"] = max(0, min(100, int(score)))
                    papers[i]["relevancy_score"] = round(papers[i]["relevancy_pct"] / 100, 2)
                except Exception:
                    papers[i]["relevancy_pct"] = 40
                    papers[i]["relevancy_score"] = 0.4
    except Exception:
        for p in papers:
            p.setdefault("relevancy_pct", 40)
            p.setdefault("relevancy_score", 0.4)

    return papers


# ─────────────────────────────────────────────
# Semantic Scholar — PRIMARY source
# ─────────────────────────────────────────────

def search_semantic_scholar(query: str, source_type: str, limit: int = 10) -> list:
    try:
        res = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={
                "query": query,
                "limit": limit,
                "fields": "title,authors,year,abstract,citationCount,externalIds,publicationVenue,openAccessPdf"
            },
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
        pdf = (p.get("openAccessPdf") or {}).get("url", "")
        results.append({
            "title": p.get("title", ""),
            "authors": ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3]),
            "year": year,
            "abstract": p.get("abstract", ""),
            "doi": doi,
            "venue": (p.get("publicationVenue") or {}).get("name", ""),
            "source": "Semantic Scholar",
            "citation_count": citations,
            "relevancy_score": 0.5,
            "relevancy_pct": 50,
            "source_type": source_type,
            "is_exception": is_exc,
            "pdf_url": pdf or (f"https://doi.org/{doi}" if doi else ""),
        })
    return results


# ─────────────────────────────────────────────
# PubMed — SECONDARY source (biomedical/food science)
# ─────────────────────────────────────────────

def search_pubmed(query: str, source_type: str, limit: int = 8) -> list:
    try:
        res = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmax": limit,
                    "retmode": "json", "sort": "relevance"},
            timeout=10
        )
        ids = res.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        time.sleep(0.3)
        res2 = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
            timeout=10
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
            "year": year,
            "abstract": "",
            "doi": doi,
            "venue": p.get("source", ""),
            "source": "PubMed",
            "citation_count": 0,
            "relevancy_score": 0.5,
            "relevancy_pct": 50,
            "source_type": source_type,
            "is_exception": is_exc,
            "pdf_url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
        })
    return results


# ─────────────────────────────────────────────
# MASTER SEARCH
# ─────────────────────────────────────────────

def search_all_sources(topic: str, objective: str, gap: str = "") -> list:

    # Step 1: Gemini generates specific queries
    queries = generate_search_queries(topic, objective, gap)
    source_type = classify_source_type(topic, objective)

    # Step 2: Search Semantic Scholar + PubMed only
    all_results = []
    seen_titles = set()

    for query in queries:
        # Semantic Scholar — primary, more results
        for r in search_semantic_scholar(query, source_type, limit=8):
            key = r["title"].lower().strip()[:70]
            if key and key not in seen_titles and len(r["title"]) > 10:
                seen_titles.add(key)
                all_results.append(r)

        # PubMed — secondary
        for r in search_pubmed(query, source_type, limit=5):
            key = r["title"].lower().strip()[:70]
            if key and key not in seen_titles and len(r["title"]) > 10:
                seen_titles.add(key)
                all_results.append(r)

        time.sleep(0.3)

    if not all_results:
        return []

    # Step 3: Gemini scores relevancy — strict
    scored = gemini_score_papers(all_results, topic, objective, gap)

    # Step 4: Sort by relevancy + citations
    scored.sort(
        key=lambda x: (x.get("relevancy_pct", 0), x.get("citation_count", 0)),
        reverse=True
    )

    # Step 5: Filter — min 40% relevancy, at least 10 results
    relevant = [p for p in scored if p.get("relevancy_pct", 0) >= 40]
    if len(relevant) < 10:
        relevant = scored[:20]

    return relevant[:25]
