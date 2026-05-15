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
# DOMAIN QUERY TEMPLATES
# Used as few-shot examples to guide Gemini
# ─────────────────────────────────────────────

DOMAIN_TEMPLATES = {
    "food_science_halal": {
        "keywords": ["halal", "food authentication", "food fraud", "lard", "adulteration",
                     "GC-MS", "GCMS", "lipid", "fatty acid", "edible oil"],
        "example_queries": [
            "GC-MS halal authentication lard detection",
            "lipid profiling lard adulteration detection",
            "machine learning edible oil classification",
            "FAME chemometrics food authentication",
            "PCA PLS-DA oil adulteration",
            "fatty acid ratio lard pork detection",
            "OPLS-DA lipid profiling discrimination",
            "SVM random forest food fraud detection",
            "lard adulteration vegetable oil GC-MS",
            "halal food verification chromatography",
        ]
    },
    "biomedical": {
        "keywords": ["disease", "clinical", "patient", "drug", "treatment", "diagnosis",
                     "biomarker", "cancer", "therapy", "genomics", "proteomics"],
        "example_queries": [
            "machine learning disease diagnosis prediction",
            "biomarker identification clinical study",
            "deep learning medical image classification",
            "drug response prediction genomics",
            "protein expression cancer biomarker",
        ]
    },
    "computer_science_ml": {
        "keywords": ["neural network", "deep learning", "NLP", "computer vision",
                     "transformer", "BERT", "classification", "reinforcement learning"],
        "example_queries": [
            "transformer model NLP text classification",
            "convolutional neural network image recognition",
            "reinforcement learning optimization policy",
            "BERT fine-tuning sentiment analysis",
            "graph neural network node classification",
        ]
    },
    "environmental": {
        "keywords": ["climate", "pollution", "environmental", "ecosystem", "carbon",
                     "remote sensing", "biodiversity", "water quality", "soil"],
        "example_queries": [
            "remote sensing land use classification",
            "water quality prediction machine learning",
            "carbon emission climate model prediction",
            "biodiversity assessment environmental monitoring",
            "soil contamination detection spectroscopy",
        ]
    },
    "social_science": {
        "keywords": ["survey", "qualitative", "quantitative", "behaviour", "perception",
                     "attitude", "education", "policy", "society", "culture"],
        "example_queries": [
            "student learning outcome assessment",
            "policy implementation educational system",
            "consumer behaviour purchase intention",
            "social media influence perception study",
            "qualitative interview thematic analysis",
        ]
    },
    "engineering": {
        "keywords": ["structural", "material", "sensor", "IoT", "optimization",
                     "finite element", "simulation", "fabrication", "composite"],
        "example_queries": [
            "structural optimization finite element analysis",
            "IoT sensor data anomaly detection",
            "composite material mechanical properties",
            "simulation modelling engineering system",
            "machine learning predictive maintenance",
        ]
    },
}


def detect_domain(topic: str, objective: str, field: str = "") -> str:
    """Detect which domain template to use based on research context."""
    combined = (topic + " " + objective + " " + field).lower()
    scores = {}
    for domain, config in DOMAIN_TEMPLATES.items():
        hits = sum(1 for kw in config["keywords"] if kw.lower() in combined)
        scores[domain] = hits
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def generate_search_queries(topic: str, objective: str, gap: str = "") -> list:
    """Gemini generates targeted queries using domain templates as examples."""

    domain = detect_domain(topic, objective)
    example_queries = DOMAIN_TEMPLATES.get(domain, {}).get("example_queries", [])
    examples_str = json.dumps(example_queries[:6])

    prompt = f"""You are an expert academic research librarian.

A researcher needs highly specific academic paper search queries.

RESEARCH CONTEXT:
Topic: {topic}
Objective: {objective}
Gap: {gap or "Not specified"}

DOMAIN DETECTED: {domain}

Here are example queries from this domain for reference style:
{examples_str}

YOUR TASK: Generate 8 NEW specific search queries for THIS researcher's exact topic.

STRICT RULES:
- 3-6 words per query
- Use EXACT scientific/technical terms from the topic and objective
- Be VERY specific — match terms that appear in academic paper titles
- Cover 8 different angles: core method, specific technique, application domain, comparison study, materials/subjects, analytical method, ML/statistical method, recent advances
- Do NOT copy the example queries — generate NEW ones specific to this research
- Do NOT use generic terms like "review", "overview", "introduction"

Return ONLY a JSON array of 8 strings. No explanation. No markdown."""

    try:
        response = model.generate_content(prompt)
        raw = re.sub(r"```json|```", "", response.text.strip()).strip()
        queries = json.loads(raw)
        if isinstance(queries, list) and len(queries) >= 4:
            return [q.strip() for q in queries if isinstance(q, str)][:8]
    except Exception:
        pass

    # Fallback — use domain template queries directly
    if example_queries:
        return example_queries[:6]

    # Last resort fallback
    words = [w for w in (topic + " " + objective).split()
             if len(w) > 4 and w.lower() not in
             {"using", "based", "approach", "study", "research",
              "analysis", "towards", "within", "their", "which"}]
    return [" ".join(words[i:i+4]) for i in range(0, min(len(words), 24), 3)][:6]


def classify_source_type(topic: str, objective: str) -> str:
    method_keywords = [
        "method", "technique", "algorithm", "model", "result", "finding",
        "analysis", "experiment", "performance", "accuracy", "detection",
        "classification", "gcms", "gc-ms", "ml", "machine learning",
        "deep learning", "neural", "profiling", "chromatography", "spectroscopy",
        "extraction", "derivatisation", "multivariate", "PCA", "PLS"
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

Score each paper 0-100 for relevance to this SPECIFIC research:
- 85-100: Directly relevant — same method, same domain, same materials/substances
- 60-84: Relevant — same domain OR same method, different application
- 30-59: Partially relevant — related field, useful as background only
- 0-29: NOT relevant — different domain, coincidental keyword match

STRICT EXAMPLES:
- Finance paper for food science study = 0
- Tourism paper for chemistry study = 0
- Halal tourism for halal food authentication = 15 MAX (different domain)
- GC-MS food paper for GC-MS halal study = 80+
- ML classification paper for ML food fraud = 70+

Papers to score:
{paper_list}

Return ONLY a JSON array of {min(len(papers), 25)} integer scores.
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

    queries = generate_search_queries(topic, objective, gap)
    source_type = classify_source_type(topic, objective)

    all_results = []
    seen_titles = set()

    for query in queries:
        for r in search_semantic_scholar(query, source_type, limit=8):
            key = r["title"].lower().strip()[:70]
            if key and key not in seen_titles and len(r["title"]) > 10:
                seen_titles.add(key)
                all_results.append(r)

        for r in search_pubmed(query, source_type, limit=5):
            key = r["title"].lower().strip()[:70]
            if key and key not in seen_titles and len(r["title"]) > 10:
                seen_titles.add(key)
                all_results.append(r)

        time.sleep(0.3)

    if not all_results:
        return []

    # Gemini scores relevancy
    scored = gemini_score_papers(all_results, topic, objective, gap)

    # Sort by relevancy + citations
    scored.sort(
        key=lambda x: (x.get("relevancy_pct", 0), x.get("citation_count", 0)),
        reverse=True
    )

    # Keep >= 40% relevancy, minimum 10 results
    relevant = [p for p in scored if p.get("relevancy_pct", 0) >= 40]
    if len(relevant) < 10:
        relevant = scored[:20]

    return relevant[:25]
