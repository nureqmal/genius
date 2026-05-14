import os
import json
import re
import google.generativeai as genai
import streamlit as st

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


def _call_gemini(prompt: str) -> str:
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"[Gemini Error: {str(e)}]"


def analyse_paper(paper: dict) -> dict:
    prompt = f"""You are an academic research assistant. Analyse this research paper and extract structured information.

Title: {paper['title']}
Authors: {paper.get('authors', 'Unknown')}
Year: {paper.get('year', 'Unknown')}
Abstract: {paper.get('abstract', 'No abstract available.')}

Return ONLY a JSON object with these exact keys (no markdown, no explanation):
{{
  "summary": "2-3 sentence summary of what this paper is about",
  "key_findings": "The main results or contributions in 2-3 sentences",
  "methodology": "The research method or approach used, 1-2 sentences",
  "contribution_type": "conceptual OR empirical OR review OR methodological"
}}"""
    raw = _call_gemini(prompt)
    try:
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception:
        return {
            "summary": "Could not extract summary.",
            "key_findings": "Could not extract findings.",
            "methodology": "Could not extract methodology.",
            "contribution_type": "unknown"
        }


def detect_research_gap(topic: str, objective: str, papers: list, existing_gap: str = "") -> str:
    paper_summaries = "\n".join([
        f"- [{p.get('year', '?')}] {p.get('paper_title', p.get('title', ''))} : {p.get('extracted_findings', p.get('abstract', ''))[:200]}"
        for p in papers[:12]
    ])
    if existing_gap:
        prompt = f"""You are a senior academic researcher. Validate, refine, and expand the researcher's proposed gap based on the literature below.

Topic: {topic}
Objective: {objective}
Researcher's proposed gap: {existing_gap}

Literature:
{paper_summaries}

Write a clear academic research gap statement (3-5 sentences)."""
    else:
        prompt = f"""You are a senior academic researcher. Identify the most significant research gap from the literature below.

Topic: {topic}
Objective: {objective}

Literature:
{paper_summaries}

Write a clear academic research gap statement (3-5 sentences)."""
    return _call_gemini(prompt)


def build_intext(paper: dict) -> str:
    authors = paper.get("authors", "Unknown")
    author_parts = [a.strip() for a in authors.split(",")]
    year = paper.get("year", "n.d.")
    if len(author_parts) >= 3:
        last_name = author_parts[0].split()[-1]
        return f"({last_name} et al., {year})"
    elif len(author_parts) == 2:
        l1 = author_parts[0].split()[-1]
        l2 = author_parts[1].split()[-1]
        return f"({l1} & {l2}, {year})"
    else:
        last_name = author_parts[0].split()[-1] if author_parts else "Unknown"
        return f"({last_name}, {year})"


STYLE_INSTRUCTIONS = {
    "formal_academic": (
        "Write in a formal academic style: third-person, passive voice where appropriate, "
        "precise discipline-specific language. Avoid contractions and first-person pronouns."
    ),
    "semi_formal": (
        "Write in a semi-formal academic style: clear and accessible, mix of active and passive voice, "
        "readable without sacrificing scholarly rigour."
    ),
    "humanized": (
        "Write in a humanized academic style: natural flow, active voice preferred, reads like a "
        "knowledgeable human researcher wrote it — not an AI. Avoid generic transitions like "
        "'Furthermore' or 'Moreover' at every sentence start. Vary sentence structure."
    ),
}

SECTION_PROMPTS = {
    "introduction": """Write an Introduction section for a research paper.

Topic: {topic}
Objective: {objective}
Research Gap: {gap}

Available sources (use for in-text citations):
{sources_block}

Instructions:
- Start broad, narrow to specific problem, end with research objective
- Insert in-text citations naturally where claims are made
- Format: (Author et al., Year) or (Author & Author, Year)
- Do NOT cite sources not listed above
- Length: 4-6 paragraphs
- {style}""",

    "literature_review": """Write a Literature Review section for a research paper.

Topic: {topic}
Objective: {objective}
Research Gap: {gap}

Papers to synthesise:
{sources_block}

Instructions:
- Organise thematically, not paper-by-paper
- Compare, contrast, and synthesise findings
- Every factual claim must have an in-text citation
- Conclude by highlighting the research gap
- Length: 5-8 paragraphs
- {style}""",

    "methodology": """Write a Methodology section for a research paper.

Topic: {topic}
Objective: {objective}

Methodological approaches from literature:
{sources_block}

Instructions:
- Describe the methodology in detail
- Justify choices by referencing prior work
- Include: research design, data collection, analysis technique
- Length: 4-6 paragraphs
- {style}""",

    "results_discussion": """Write a Results and Discussion section for a research paper.

Topic: {topic}
Objective: {objective}
Research Gap addressed: {gap}

Key findings from literature:
{sources_block}

Instructions:
- Present findings, contextualise against prior literature
- Discuss agreement and disagreement with existing work
- Address the research gap
- Length: 5-7 paragraphs
- {style}""",

    "conclusion": """Write a Conclusion section for a research paper.

Topic: {topic}
Objective: {objective}
Research Gap addressed: {gap}

Instructions:
- Summarise key contributions
- Revisit the research gap and how this work addresses it
- State limitations
- Suggest future research directions
- Length: 3-4 paragraphs
- {style}""",
}


def write_section(section: str, topic: str, objective: str, gap: str, papers: list, style_preset: str = "formal_academic") -> str:
    style = STYLE_INSTRUCTIONS.get(style_preset, STYLE_INSTRUCTIONS["formal_academic"])
    sources_lines = []
    for p in papers:
        intext = build_intext(p)
        summary = p.get("extracted_findings") or p.get("abstract", "")[:200]
        sources_lines.append(f"- {intext} | {p.get('paper_title', p.get('title', ''))} ({p.get('year', '?')}) | {summary}")
    sources_block = "\n".join(sources_lines) if sources_lines else "No sources provided."
    template = SECTION_PROMPTS.get(section, "")
    if not template:
        return "[Unknown section]"
    prompt = template.format(
        topic=topic, objective=objective,
        gap=gap or "Not specified.",
        sources_block=sources_block, style=style,
    )
    return _call_gemini(prompt)


def detect_contradictions(papers: list) -> list:
    if len(papers) < 2:
        return []
    summaries = "\n".join([
        f"[{i+1}] {p.get('paper_title', p.get('title',''))} ({p.get('year','?')}): {p.get('extracted_findings', '')[:150]}"
        for i, p in enumerate(papers[:10])
    ])
    prompt = f"""Review these paper summaries and identify contradictory findings.

{summaries}

List only genuine contradictions:
- Paper X vs Paper Y: [description]

If none, respond: "No contradictions detected."
Plain text only, no markdown."""
    result = _call_gemini(prompt)
    if "No contradictions" in result:
        return []
    return [l.strip() for l in result.split("\n") if l.strip().startswith("-")]
