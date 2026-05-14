import requests


def fetch_doi_metadata(doi: str) -> dict:
    if not doi:
        return {}
    try:
        res = requests.get(f"https://api.crossref.org/works/{doi}", timeout=8,
                           headers={"User-Agent": "ResearchAI/1.0"})
        if res.status_code != 200:
            return {}
        return res.json().get("message", {})
    except Exception:
        return {}


def format_apa(paper: dict, meta: dict = None) -> str:
    authors = paper.get("authors", "Unknown Author")
    year = paper.get("year", "n.d.")
    title = paper.get("paper_title") or paper.get("title", "Untitled")
    doi = paper.get("doi", "")
    journal = ""
    volume = ""
    if meta:
        container = meta.get("container-title", [])
        journal = container[0] if container else ""
        volume = meta.get("volume", "")
    author_parts = [a.strip() for a in authors.split(",")]
    parts = []
    for a in author_parts:
        name_parts = a.strip().split()
        if len(name_parts) >= 2:
            last = name_parts[-1]
            initials = ". ".join(n[0] for n in name_parts[:-1]) + "."
            parts.append(f"{last}, {initials}")
        else:
            parts.append(a)
    if len(parts) > 1:
        formatted_authors = ", ".join(parts[:-1]) + ", & " + parts[-1]
    else:
        formatted_authors = parts[0] if parts else authors
    citation = f"{formatted_authors} ({year}). {title}."
    if journal:
        citation += f" *{journal}*"
        if volume:
            citation += f", *{volume}*"
        citation += "."
    if doi:
        citation += f" https://doi.org/{doi}"
    return citation


def format_ieee(paper: dict, meta: dict = None) -> str:
    authors = paper.get("authors", "Unknown")
    year = paper.get("year", "n.d.")
    title = paper.get("paper_title") or paper.get("title", "Untitled")
    doi = paper.get("doi", "")
    journal = ""
    volume = ""
    if meta:
        container = meta.get("container-title", [])
        journal = container[0] if container else ""
        volume = meta.get("volume", "")
    author_parts = [a.strip() for a in authors.split(",")]
    parts = []
    for a in author_parts:
        name_parts = a.strip().split()
        if len(name_parts) >= 2:
            initials = ". ".join(n[0] for n in name_parts[:-1]) + "."
            parts.append(f"{initials} {name_parts[-1]}")
        else:
            parts.append(a)
    formatted_authors = " and ".join(parts)
    citation = f'{formatted_authors}, "{title},"'
    if journal:
        citation += f" *{journal}*,"
    if volume:
        citation += f" vol. {volume},"
    citation += f" {year}."
    if doi:
        citation += f" doi: {doi}"
    return citation


def format_mla(paper: dict, meta: dict = None) -> str:
    authors = paper.get("authors", "Unknown")
    year = paper.get("year", "n.d.")
    title = paper.get("paper_title") or paper.get("title", "Untitled")
    doi = paper.get("doi", "")
    journal = ""
    if meta:
        container = meta.get("container-title", [])
        journal = container[0] if container else ""
    author_parts = [a.strip() for a in authors.split(",")]
    first = author_parts[0] if author_parts else "Unknown"
    name_parts = first.strip().split()
    if len(name_parts) >= 2:
        first_formatted = f"{name_parts[-1]}, {' '.join(name_parts[:-1])}"
    else:
        first_formatted = first
    if len(author_parts) > 2:
        formatted_authors = first_formatted + ", et al."
    elif len(author_parts) == 2:
        formatted_authors = first_formatted + f", and {author_parts[1]}"
    else:
        formatted_authors = first_formatted
    citation = f'{formatted_authors}. "{title}."'
    if journal:
        citation += f" *{journal}*,"
    citation += f" {year}."
    if doi:
        citation += f" https://doi.org/{doi}"
    return citation


def generate_all_citations(papers: list, style: str = "apa") -> list:
    refs = []
    for i, p in enumerate(papers):
        meta = fetch_doi_metadata(p.get("doi", "")) if p.get("doi") else {}
        if style == "apa":
            refs.append(format_apa(p, meta))
        elif style == "ieee":
            refs.append(f"[{i+1}] " + format_ieee(p, meta))
        elif style == "mla":
            refs.append(format_mla(p, meta))
    return refs
