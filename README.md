ATS Resume & Cover Letter Builder (Truthful, Consulting-Style)

A minimal, local-first CLI that ingests a job description and a candidate profile, selects strictly truthful evidence-backed bullets, and renders an ATS-friendly consulting-style resume and cover letter in DOCX (with optional PDF export on Windows).

- No fabrication: selects/paraphrases only provided, source-linked content.
- Single-column consulting/enterprise style (Calibri/Cambria/Arial), ATS-safe.
- Outputs: `.docx` canonical, optional `.pdf` via Word/LibreOffice if available.

Features (MVP)
- Parse job description text and candidate JSON.
- Score and select candidate bullets aligned to JD keywords.
- Generate resume sections (Experience, Education, Skills) and a short cover letter.
- Enforce truthfulness by linking every bullet to its `source_ids`.
- Render clean DOCX formatting (margins, fonts, bullet lists). Optional PDF export.

Project Structure
```
.
├─ data/
│  ├─ sample_job.txt
│  └─ sample_candidate.json
├─ src/
│  └─ ats_builder/
│     ├─ __init__.py
│     ├─ schemas.py
│     ├─ ingest.py
│     ├─ match.py
│     ├─ generate.py
│     ├─ render.py
│     ├─ evaluate.py
│     ├─ review.py
│     ├─ docs.py
│     ├─ docs_to_json.py
│     ├─ vectorstore.py
│     ├─ index_build.py
│     └─ cli.py
└─ requirements.txt
```

Install
Create a virtual environment and install dependencies. Network installs may be restricted; if so, you can still read the code and adapt.

```
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

If `docx2pdf` or Word is not available, PDF export will be skipped. On non-Windows, install LibreOffice to enable `soffice --headless` conversion.

Usage
Run the CLI with the provided sample data:

```
python -m ats_builder.cli \
  --job data/sample_job.txt \
  --candidate data/sample_candidate.json \
  --out out
```

Outputs (created under `out/`):
- `Firstname_Lastname_Role_Company_resume.docx`
- `Firstname_Lastname_Role_Company_cover_letter.docx`
- Optional `.pdf` variants when conversion is available.
 - A `..._trace.json` file with transparency info (sources, evaluation, edits).

URL Ingestion
- You can also supply a job posting URL (the tool will scrape and extract the main text):

```
python -m ats_builder.cli \
  --job-url "https://example.com/job/123" \
  --candidate data/sample_candidate.json \
  --out out
```

Scraping tries `trafilatura` or `readability-lxml` if installed, otherwise falls back to BeautifulSoup text extraction. If fetching fails (e.g., network restrictions), the job text will include the error message so you can paste the JD manually.

Browser Scrape (JS-rendered pages like Ashby)
- For sites that render the description via JavaScript (e.g., Ashby), enable Playwright-based scraping:
```
pip install -r requirements.txt
playwright install  # one-time, downloads headless browsers

python -m ats_builder.cli \
  --job-url "https://jobs.ashbyhq.com/..." \
  --browser-scrape --browser-wait "main" \
  --candidate data/sample_candidate.json \
  --out out --show-jd --confirm-jd
```
- The scraper also checks LD+JSON (JobPosting.description) when present for high-fidelity extraction.

Semantic Matching
- Bullet selection blends semantic similarity (TF‑IDF cosine) with keyword overlap for better alignment to the JD. If `scikit-learn` is not installed, a lightweight token‑overlap fallback is used automatically.

Evaluator
- The CLI runs a keyword coverage evaluator before export and reports:
  - Coverage ratio across JD keywords
  - Top missing keywords (to address if truthful/relevant)
  - Suggestions (e.g., add relevant skills or bullets)
- This info is also stored in the `..._trace.json` file.

Interactive Review (Optional)
- Add `--review` to refine sections in an interactive flow:
  - Edit header details, bullets per role, skills list, and each cover letter paragraph.
  - You can add new bullets (marked with `source_id: "user_added"` in the trace).
- Add `--notes path/to/notes.txt` to weave a short personal note into the cover letter.

Examples
```
python -m ats_builder.cli \
  --job-url "https://example.com/job/123" \
  --candidate data/sample_candidate.json \
  --out out \
  --review \
  --notes data/personal_note.txt
```

Style and Truthfulness
- Resume: selects and formats existing bullets; no metric/title/tool/date fabrication.
- Cover letter: natural, concise tone with concrete highlights from your own bullets; optional personal note; no invented facts.

Optional LLM Refinement (Perplexity)
- You can enable LLM rewriting for bullets and the cover letter to improve clarity, flow, and natural tone. Guardrails:
  - Strict no-fabrication instruction in the prompt; only paraphrase given bullets.
  - Numeric guard: if the rewrite introduces numbers not in the original bullet, the tool reverts that bullet.
- Set an API key in your environment before running (PowerShell):
  - `$env:PERPLEXITY_API_KEY = "<your_key>"`
- Example usage:
```
python -m ats_builder.cli \
  --job-url "https://example.com/job/123" \
  --candidate data/my_candidate.json \
  --out out \
  --llm --llm-model sonar-reasoning-pro --llm-temp 0.4
```
- If the API call fails or the key is not set, the tool falls back to non-LLM behavior automatically.

Build Candidate JSON From Your Docs
- Convert a folder of resumes/cover letters (PDF, DOCX, TXT) into `candidate.json`:

```
python -m ats_builder.docs_to_json \
  --input path/to/your_docs \
  --out data/my_candidate.json \
  --name "Your Name" --email "you@example.com" --phone "+1-555-..." --location "City, ST" \
  --interactive --prefer "BestResume2025"
```

- The parser extracts Experience/Education/Skills via heuristics and keeps bullets with a `source_id` of the original filename. You can manually refine the resulting JSON if needed.
- For best results, use resumes with clear section headers: “Experience”, “Education”, “Skills”. Bullets should start with standard markers (•, -, *, 1.).

One-Page Option
- Generate a tighter one-page resume by reducing bullet budgets automatically:
```
python -m ats_builder.cli --job-url "https://example.com/job/123" --candidate data/my_candidate.json --out out --one-page
```

Vector Store (Retrieval)
- Build a local TF‑IDF index from your candidate JSON to retrieve the most relevant bullets/skills during LLM letter drafting:
```
python -m ats_builder.index_build --candidate data/my_candidate.json --out .index/candidate_index.pkl
python -m ats_builder.cli --job-url "https://example.com/job/123" --candidate data/my_candidate.json --out out --llm --index .index/candidate_index.pkl
```
- If `--index` is provided but missing and `--build-index` is passed, the CLI builds the index on the fly from the candidate JSON.
- FAISS: Not required for MVP. This tool ships with TF‑IDF; FAISS can be added later if you install the dependencies (we’ll deduplicate chunks to avoid repeated content in retrieval).

Data Contracts
- Job description: plain text file (or paste into a file) containing the posting content.
- Candidate profile (`JSON`): see `data/sample_candidate.json`.

Key fields:
- `identity`: name, email, phone, location, links
- `work_experience[]`: company, role, start/end, bullets (each with `text`, `source_ids`), tools/skills
- `education[]`, `certifications[]`, `projects[]` (optional)
- `skills`: hard/soft lists
- `artifacts[]`: optional backing sources `{source_id, type, uri_or_text}`

Truthfulness Guarantees
- Selection-only: the tool selects existing bullets; optional light paraphrase keeps facts intact.
- Every bullet in the final resume carries forward its `source_ids` in an internal trace file.
- No invented dates/metrics/titles/tools. If not present in sources, it won’t appear in output.

Consulting-Style Formatting
- Single column; 0.75–1.0" margins; left-aligned; no tables for body content.
- Fonts: Calibri 11 (default), with consistent styles for headings and bullets.
- Bullet style: Word built-in list bullets; concise 1–2 lines each.

Next Steps (Beyond MVP)
- JD scraper (URL ingestion) with `trafilatura` (optional).
- Semantic matching with sentence transformers.
- Review UI showing bullet source traces and diffs.
- Multi-job batching and saved projects.

License
Internal use by default. Add a license if you plan to distribute.

JD Preview and Confirmation
- Preview and/or save the extracted job description before generation to ensure accuracy:
```
python -m ats_builder.cli \
  --job-url "https://example.com/job/123" \
  --candidate data/my_candidate.json \
  --out out \
  --show-jd --jd-save data/jd_extracted.txt --confirm-jd
```
- If you choose not to proceed at confirmation, pass a corrected JD via `--job <path>`.

FAISS Retrieval (Optional)
- Install: `pip install faiss-cpu sentence-transformers numpy scikit-learn`
- Build from candidate JSON:
```
python -m ats_builder.faiss_build --candidate data/my_candidate.json --out .index/candidate.faiss.pkl --model sentence-transformers/all-MiniLM-L6-v2
```
- Use during generation:
```
python -m ats_builder.cli \
  --job-url "https://example.com/job/123" \
  --candidate data/my_candidate.json \
  --out out \
  --llm --retrieval faiss --faiss .index/candidate.faiss.pkl
```

LinkedIn Ingestion (Optional)
- From your LinkedIn Data Export, extract `Profile.json` and pass it to the builder:
```
python -m ats_builder.docs_to_json \
  --input path/to/your_docs \
  --linkedin path/to/Profile.json \
  --out data/my_candidate.json \
  --interactive
```
- Merge policy: LinkedIn provides titles/dates/education structure; resume bullets remain your authoritative content. Entries are deduplicated.

Full Command Reference (Quick Copy)
- Build candidate JSON from a folder (PDF/DOCX/TXT):
  - `python -m ats_builder.docs_to_json --input ".\Mahtab" --out .\data\mahtab_candidate.json --interactive`
  - Prefer a specific resume file: add `--prefer "PrimaryResume"`
  - Merge LinkedIn profile export (Profile.json) if available: `--linkedin ".\Mahtab\Profile.json"`

- Parse report (see what got extracted per file):
  - `python -m ats_builder.parse_report --input ".\Mahtab" --out .\data\parse_report.json`

- Build TF‑IDF index (optional):
  - `python -m ats_builder.index_build --candidate .\data\mahtab_candidate.json --out .index\candidate_index.pkl`

- Build FAISS index (optional; requires faiss-cpu and sentence-transformers):
  - `python -m ats_builder.faiss_build --candidate .\data\mahtab_candidate.json --out .index\candidate.faiss.pkl --model sentence-transformers/all-MiniLM-L6-v2`

- Generate (URL with Playwright render; preview+confirm JD; timestamped files; JD auto-save):
  - `python -m ats_builder.cli --job-url "<JD URL>" --browser-scrape --browser-wait "main" --candidate .\data\mahtab_candidate.json --out .\out --show-jd --confirm-jd --jd-save-auto --append-datetime`

- Enable LLM (Perplexity) with retrieval + notes prompt + review:
  - Set key: `$env:PERPLEXITY_API_KEY = "<your_key>"`
  - `python -m ats_builder.cli --job-url "<JD URL>" --browser-scrape --browser-wait "main" --candidate .\data\mahtab_candidate.json --out .\out --llm --llm-model sonar-reasoning-pro --llm-temp 0.4 --retrieval faiss --faiss .index\candidate.faiss.pkl --prompt-notes --review --show-jd --confirm-jd --jd-save-auto --append-datetime`

- Minimal LLM only (no retrieval):
  - `python -m ats_builder.cli --job-url "<JD URL>" --browser-scrape --candidate .\data\mahtab_candidate.json --out .\out --llm --llm-model sonar-reasoning-pro --llm-temp 0.4 --append-datetime`

Key Flags
- Job: `--job`, `--job-url`, `--browser-scrape`, `--browser-wait`, `--browser-timeout`, `--show-jd`, `--jd-save`, `--jd-save-auto`, `--confirm-jd`.
- Candidate: `--candidate`, `--title`, `--company`, `--location`, `--notes`, `--prompt-notes`.
- Output/Layout: `--out`, `--no-pdf`, `--append-datetime`, `--one-page`.
- Retrieval: `--retrieval none|tfidf|faiss`, `--index`, `--build-index`, `--faiss`.
- LLM: `--llm`, `--llm-model`, `--llm-temp` (requires `PERPLEXITY_API_KEY`).
- Review/Eval: `--review` (interactive section edits; evaluation always runs and stores in trace).
