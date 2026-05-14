# 🔬 ResearchAI — Setup Guide

## Quick Start (3 steps)

### Step 1 — Supabase Setup
1. Go to [supabase.com](https://supabase.com) → Create new project (free)
2. Go to **SQL Editor** → paste the contents of `supabase_schema.sql` → Run
3. Go to **Project Settings → API** → copy:
   - `Project URL` → this is your `SUPABASE_URL`
   - `anon public` key → this is your `SUPABASE_ANON_KEY`

### Step 2 — Gemini API Key
1. Go to [aistudio.google.com](https://aistudio.google.com) → Get API Key (free)
2. Copy your `GEMINI_API_KEY`

### Step 3 — Deploy to Streamlit Cloud
1. Push this folder to a **GitHub repo**
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app
3. Select your repo → set **Main file path** to `app.py`
4. Go to **Advanced settings → Secrets** → paste:

```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_ANON_KEY = "your-anon-key"
GEMINI_API_KEY = "your-gemini-key"
```

5. Click **Deploy** — done!

---

## Run Locally

```bash
pip install -r requirements.txt

# Copy and fill in your keys
cp .env.example .env

streamlit run app.py
```

---

## Project Structure

```
researchai/
├── app.py                  # Main entry point
├── requirements.txt
├── supabase_schema.sql     # Run this in Supabase SQL Editor
├── .streamlit/
│   ├── config.toml         # Theme config
│   └── secrets.toml.example
├── pages/
│   ├── login.py            # Auth page
│   ├── dashboard.py        # Project list
│   ├── new_project.py      # Create project (topic/objective/gap)
│   ├── search.py           # Multi-source paper search
│   ├── analyse.py          # AI extraction + validation checkpoint
│   ├── write.py            # Section-by-section writing
│   └── export.py           # Word + PDF export
└── utils/
    ├── auth.py             # Supabase auth helpers
    ├── search.py           # Semantic Scholar, arXiv, PubMed, CrossRef
    ├── ai.py               # Gemini analysis + writing
    ├── citations.py        # APA / IEEE / MLA formatter
    ├── db.py               # Supabase CRUD
    └── export.py           # python-docx + reportlab
```

---

## Common Errors

| Error | Fix |
|---|---|
| `ModuleNotFoundError: utils` | Make sure `utils/__init__.py` and `pages/__init__.py` exist |
| `Supabase auth error` | Check SUPABASE_URL and SUPABASE_ANON_KEY in secrets |
| `Gemini API error` | Check GEMINI_API_KEY — make sure free tier is active |
| `Export fails` | Make sure `python-docx` and `reportlab` are in requirements.txt |
