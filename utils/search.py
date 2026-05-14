import requests
import time
from datetime import datetime

CURRENT_YEAR = datetime.now().year
RECENT_YEARS = 5
HIGH_CITATION_THRESHOLD = 500


def classify_source_type(query: str, objective: str) -> str:
    method_keywords = [
        "method", "methodology", "approach", "technique", "algorithm",
        "model", "framework", "result", "finding", "analysis", "experiment",
        "performance", "accuracy", "detection", "classification", "using",
        "based on", "gcms", "ml", "machine learning", "deep learning"
    ]
    combined = (query + " " + objective).lower()
    hits = sum(1 for kw in method_keywords if kw in combined)
    return "method_result" if hits >= 2 else "conceptual"


def is_recent_enough(year: int, source_type: str, citation_count: int):
    if source_type == "conceptual":
        return True, False
    if year is None:
        return True, False
    age = CURRENT_YEAR - year
    if age <= RECENT_YEARS:
        return True, False
    if citation_count >= HIGH_CITATION_THRESHOLD:
        return True, True
    return False, False


def compute_relevancy(title: str, abstract: str, query: str, objective: str) -> float:
    keywords = set((query + " " + objective).lower().split())
    stopwords = {"a", "an", "the", "and", "or", "for", "of", "in", "to", "with",
                 "using", "based", "on", "is", "are", "was", "be", "this", "that"}
    keywords -= stopwords
    if not keywords:
        return 0.5
    text = (title + " " + (abstract or "")).lower()
    hits = sum(1 for kw in keywords if kw in text)
    return round(min(hits / len(keywords), 1.0), 2)


def search_semantic_scholar(query: str, objective: str, limit: int = 10) -> list:
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,abstract,citationCount,externalIds"
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json().get("data", [])
    except Exception:
        return []

    source_type = classify_source_type(query, objective)
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
            "year": year,
            "abstract": p.get("abstract", ""),
            "doi": doi,
            "source": "Semantic Scholar",
            "citation_count": citations,
            "relevancy_score": compute_relevancy(p.get("title", ""), p.get("abstract", ""), query, objective),
            "source_type": source_type,
            "is_exception": is_exc,
            "pdf_url": f"https://doi.org/{doi}" if doi else "",
        })
    return results


def search_arxiv(query: str, objective: str, limit: int = 8) -> list:
    url = "http://export.arxiv.org/api/query"
    params = {"search_query": f"all:{query}", "start": 0, "max_results": limit, "sortBy": "relevance"}
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
    except Exception:
        return []

    import xml.etree.ElementTree as ET
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(res.text)
    entries = root.findall("atom:entry", ns)
    source_type = classify_source_type(query, objective)
    results = []
    for e in entries:
        title = (e.findtext("atom:title", "", ns) or "").strip().replace("\n", " ")
        abstract = (e.findtext("atom:summary", "", ns) or "").strip().replace("\n", " ")
        published = e.findtext("atom:published", "", ns) or ""
        year = int(published[:4]) if published else 0
        authors = ", ".join(a.text for a in e.findall("atom:author/atom:name", ns)[:3] if a.text)
        arxiv_id = (e.findtext("atom:id", "", ns) or "").split("/abs/")[-1]
        doi = ""
        for link in e.findall("atom:link", ns):
            if link.get("title") == "doi":
                doi = link.get("href", "").replace("http://dx.doi.org/", "")
        passes, is_exc = is_recent_enough(year, source_type, 0)
        if not passes:
            continue
        results.append({
            "title": title, "authors": authors, "year": year, "abstract": abstract,
            "doi": doi or arxiv_id, "source": "arXiv", "citation_count": 0,
            "relevancy_score": compute_relevancy(title, abstract, query, objective),
            "source_type": source_type, "is_exception": is_exc,
            "pdf_url": f"https://arxiv.org/abs/{arxiv_id}",
        })
    return results


def search_pubmed(query: str, objective: str, limit: int = 8) -> list:
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    try:
        res = requests.get(search_url, params={
            "db": "pubmed", "term": query, "retmax": limit, "retmode": "json", "sort": "relevance"
        }, timeout=10)
        ids = res.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        time.sleep(0.3)
        res2 = requests.get(fetch_url, params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"}, timeout=10)
        summaries = res2.json().get("result", {})
    except Exception:
        return []

    source_type = classify_source_type(query, objective)
    results = []
    for uid in ids:
        p = summaries.get(uid, {})
        if not p or uid == "uids":
            continue
        title = p.get("title", "")
        year_str = p.get("pubdate", "")[:4]
        year = int(year_str) if year_str.isdigit() else 0
        authors = ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3])
        doi = next((i.get("value", "") for i in (p.get("articleids") or []) if i.get("idtype") == "doi"), "")
        passes, is_exc = is_recent_enough(year, source_type, 0)
        if not passes:
            continue
        results.append({
            "title": title, "authors": authors, "year": year, "abstract": "",
            "doi": doi, "source": "PubMed", "citation_count": 0,
            "relevancy_score": compute_relevancy(title, "", query, objective),
            "source_type": source_type, "is_exception": is_exc,
            "pdf_url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
        })
    return results


def search_crossref(query: str, objective: str, limit: int = 8) -> list:
    url = "https://api.crossref.org/works"
    params = {"query": query, "rows": limit,
               "select": "title,author,published,DOI,abstract,is-referenced-by-count"}
    try:
        res = requests.get(url, params=params, timeout=10, headers={"User-Agent": "ResearchAI/1.0"})
        items = res.json().get("message", {}).get("items", [])
    except Exception:
        return []

    source_type = classify_source_type(query, objective)
    results = []
    for p in items:
        title = (p.get("title") or [""])[0]
        pub = p.get("published", {}).get("date-parts", [[0]])[0]
        year = pub[0] if pub else 0
        authors_raw = p.get("author") or []
        authors = ", ".join(f"{a.get('family', '')} {a.get('given', '')[:1]}" for a in authors_raw[:3])
        doi = p.get("DOI", "")
        citations = p.get("is-referenced-by-count", 0)
        abstract = p.get("abstract", "")
        passes, is_exc = is_recent_enough(year, source_type, citations)
        if not passes:
            continue
        results.append({
            "title": title, "authors": authors, "year": year, "abstract": abstract,
            "doi": doi, "source": "CrossRef", "citation_count": citations,
            "relevancy_score": compute_relevancy(title, abstract, query, objective),
            "source_type": source_type, "is_exception": is_exc,
            "pdf_url": f"https://doi.org/{doi}" if doi else "",
        })
    return results


def search_all_sources(query: str, objective: str) -> list:
    all_results = []
    all_results += search_semantic_scholar(query, objective)
    all_results += search_arxiv(query, objective)
    all_results += search_pubmed(query, objective)
    all_results += search_crossref(query, objective)
    seen = set()
    unique = []
    for r in all_results:
        key = r["title"].lower().strip()[:60]
        if key and key not in seen:
            seen.add(key)
            unique.append(r)
    unique.sort(key=lambda x: (x["relevancy_score"], x["citation_count"]), reverse=True)
    return unique
