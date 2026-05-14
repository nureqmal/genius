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
model = genai.GenerativeModel("gemini-1.5-flash")  # free tier


def _call_gemini(prompt: str) -> str:
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"[Gemini Error: {str(e)}]"


# ─────────────────────────────────────────────
# Paper Analysis (batch of 3-5 papers)
# ─────────────────────────────────────────────

def analyse_paper(paper: dict) -> dict:
    """Extract summary, findings, methodology from a single paper."""
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


# ─────────────────────────────────────────────
# Research Gap Detection
# ─────────────────────────────────────────────

def detect_research_gap(topic: str, objective: str, papers: list[dict], existing_gap: str = "") -> str:
    """Detect or validate research gap from the paper pool."""
    paper_summaries = "\n".join([
        f"- [{p.get('year', '?')}] {p['title']}: {p.get('extracted_findings', p.get('abstract', ''))[:200]}"
        for p in papers[:12]
    ])

    if existing_gap:
        prompt = f"""You are a senior academic researcher. The researcher has identified a research gap. Validate, refine, and expand it based on the literature below.

Topic: {topic}
Objective: {objective}
Researcher's proposed gap: {existing_gap}

Literature summary:
{paper_summaries}

Write a clear, academic-quality research gap statement (3-5 sentences). Confirm what is missing in the literature, why it matters, and how the proposed research addresses it. Be specific."""
    else:
        prompt = f"""You are a senior academic researcher. Based on the literature below, identify the most significant research gap.

Topic: {topic}
Objective: {objective}

Literature summary:
{paper_summaries}

Write a clear, academic-quality research gap statement (3-5 sentences). Identify what is missing, why it matters, and what future research should address. Be specific and grounded in the papers above."""

    return _call_gemini(prompt)


# ─────────────────────────────────────────────
# Citation Tracker
# ─────────────────────────────────────────────

def build_citation_key(paper: dict) -> str:
    """Returns (AuthorLastName, Year) key for in-text citation."""
    authors = paper.get("authors", "Unknown")
    first_author = authors.split(",")[0].strip().split()[-1]  # last name
    year = paper.get("year", "n.d.")
    return f"{first_author}, {year}"


def build_intext(paper: dict, multiple: bool = False) -> str:
    """Returns formatted in-text citation string."""
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


# ─────────────────────────────────────────────
# Section Writing
# ─────────────────────────────────────────────

STYLE_INSTRUCTIONS = {
    "formal_academic": (
        "Write in a formal academic style: third-person, passive voice where appropriate, "
        "precise discipline-specific language, structured argumentation. Avoid contractions, "
        "colloquialisms, and first-person pronouns."
    ),
    "semi_formal": (
        "Write in a semi-formal academic style: clear and accessible, mix of active and passive voice, "
        "readable without sacrificing scholarly rigour. Avoid overly complex jargon."
    ),
    "humanized": (
        "Write in a humanized academic style: natural flow, active voice preferred, reads like a "
        "knowledgeable human researcher wrote it — not an AI. Avoid generic transitions like "
        "'Furthermore' or 'Moreover' at the start of every sentence. Vary sentence structure. "
        "Sound confident and specific."
    ),
}

SECTION_PROMPTS = {
    "introduction": """Write an Introduction section for a research paper.

Topic: {topic}
Objective: {objective}
Research Gap: {gap}

Available sources (use these for in-text citations):
{sources_block}

Instructions:
- Start broad (contextualise the field), narrow to the specific problem, end with the research objective
- Naturally insert in-text citations where claims are made (format: Author et al., Year or Author & Author, Year)
- Do NOT cite sources that are not in the list above
- Length: 4-6 paragraphs
- {style}""",

    "literature_review": """Write a Literature Review section for a research paper.

Topic: {topic}
Objective: {objective}
Research Gap: {gap}

Papers to synthesise (include in-text citations from these):
{sources_block}

Instructions:
- Organise thematically, not paper-by-paper
- Compare, contrast, and synthesise — do not just summarise each paper
- Every factual claim must have an in-text citation (Author et al., Year)
- Conclude by highlighting the research gap
- Length: 5-8 paragraphs
- {style}""",

    "methodology": """Write a Methodology section for a research paper.

Topic: {topic}
Objective: {objective}

Methodological approaches from literature:
{sources_block}

Instructions:
- Describe the proposed/adopted methodology in detail
- Justify methodological choices by referencing prior work where relevant
- Include: research design, data collection approach, analysis technique
- Use in-text citations where referencing prior methodological decisions
- Length: 4-6 paragraphs
- {style}""",

    "results_discussion": """Write a Results and Discussion section for a research paper.

Topic: {topic}
Objective: {objective}
Research Gap addressed: {gap}

Key findings from literature to contextualise results:
{sources_block}

Instructions:
- Present findings, then contextualise against prior literature using in-text citations
- Discuss agreement and disagreement with existing work
- Address the research gap identified earlier
- Length: 5-7 paragraphs
- {style}""",

    "conclusion": """Write a Conclusion section for a research paper.

Topic: {topic}
Objective: {objective}
Research Gap addressed: {gap}

Instructions:
- Summarise the key contributions
- Revisit the research gap and explain how this work addresses it
- State limitations honestly
- Suggest future research directions
- Do NOT introduce new citations not previously used
- Length: 3-4 paragraphs
- {style}""",
}


def write_section(
    section: str,
    topic: str,
    objective: str,
    gap: str,
    papers: list[dict],
    style_preset: str = "formal_academic"
) -> str:
    """Generate a single paper section with in-text citations."""
    style = STYLE_INSTRUCTIONS.get(style_preset, STYLE_INSTRUCTIONS["formal_academic"])

    # Build sources block with intext citation format
    sources_lines = []
    for p in papers:
        intext = build_intext(p)
        summary = p.get("extracted_findings") or p.get("abstract", "")[:200]
        sources_lines.append(
            f"- {intext} | {p['title']} ({p.get('year', '?')}) | {summary}"
        )
    sources_block = "\n".join(sources_lines) if sources_lines else "No sources provided."

    template = SECTION_PROMPTS.get(section, "")
    if not template:
        return "[Unknown section]"

    prompt = template.format(
        topic=topic,
        objective=objective,
        gap=gap or "Not specified.",
        sources_block=sources_block,
        style=style,
    )

    return _call_gemini(prompt)


# ─────────────────────────────────────────────
# Contradiction Detector
# ─────────────────────────────────────────────

def detect_contradictions(papers: list[dict]) -> list[str]:
    """Flag potential contradictions between papers in the pool."""
    if len(papers) < 2:
        return []

    summaries = "\n".join([
        f"[{i+1}] {p['title']} ({p.get('year','?')}): {p.get('extracted_findings', '')[:150]}"
        for i, p in enumerate(papers[:10])
    ])

    prompt = f"""You are a research analyst. Review these paper summaries and identify any contradictory findings or conflicting conclusions.

{summaries}

List only genuine contradictions (not just different perspectives). Format as:
- Paper X vs Paper Y: [brief description of contradiction]

If no contradictions found, respond with: "No contradictions detected."
Return plain text, no markdown formatting."""

    result = _call_gemini(prompt)
    if "No contradictions" in result:
        return []
    lines = [l.strip() for l in result.split("\n") if l.strip().startswith("-")]
    return lines
