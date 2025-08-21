from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple, List, Optional

from .schemas import candidate_from_dict, job_from_text, Candidate, JobPosting


STOPWORDS = {
    "the","and","to","of","in","a","for","with","on","is","as","by","or","at","an","be","are","from","that","this","will","we",
    "our","your","you","us","it","into","across","using","use","team","work","role","company","llc","inc","co","corp"
}


def read_job_text(path: str) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8", errors="ignore")


def extract_keywords(text: str, top_k: int = 40) -> List[str]:
    # Simple keyword extraction: frequency-based, alnum tokens, lowercased, filtered stopwords, len>=2
    from collections import Counter
    import re

    tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9+#\.\-/]+", text)]
    tokens = [t.strip(".-/") for t in tokens if t and t.lower() not in STOPWORDS and len(t) > 1]
    counts = Counter(tokens)
    # Favor tech/skill tokens by simple heuristics
    for t in list(counts.keys()):
        if any(ch.isupper() for ch in t):
            counts[t] += 1
        if any(c in t for c in ["sql","aws","azure","gcp","etl","crm","erp","sap","python","java","excel","saas","api","ml","ai","pm"]):
            counts[t] += 1
    return [w for w, _ in counts.most_common(top_k)]


def load_candidate(path: str) -> Candidate:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return candidate_from_dict(data)


def load_job(path: str, title: str | None = None, company: str | None = None, location: str | None = None) -> JobPosting:
    text = read_job_text(path)
    keywords = extract_keywords(text)
    return job_from_text(text, title=title, company=company, location=location, keywords=keywords)


def _extract_main_text_from_html(html: str) -> str:
    # Try structured data (LD+JSON) first for JobPosting.description
    try:
        from bs4 import BeautifulSoup  # type: ignore
        import json as _json
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                data = _json.loads(tag.string or "")
            except Exception:
                continue
            # Handle list or single dict
            items = data if isinstance(data, list) else [data]
            for it in items:
                t = (it.get("@type") or it.get("type") or "").lower()
                if "jobposting" in t and it.get("description"):
                    # Strip HTML tags from description if any
                    desc_html = it.get("description")
                    desc = BeautifulSoup(desc_html, "html.parser").get_text("\n")
                    if desc and len(desc.split()) > 40:
                        return desc
    except Exception:
        pass

    # Try trafilatura if available
    try:
        import trafilatura  # type: ignore
        extracted = trafilatura.extract(html)  # returns None if fails
        if extracted:
            return extracted
    except Exception:
        pass
    # Try readability-lxml if available
    try:
        from readability import Document  # type: ignore
        doc = Document(html)
        content_html = doc.summary()
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(content_html, "html.parser")
        text = soup.get_text("\n")
        if text.strip():
            return text
    except Exception:
        pass
    # Fallback: basic BeautifulSoup text
    try:
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(html, "html.parser")
        # Remove script/style
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text("\n")
        return text
    except Exception:
        return html


def load_job_from_url(url: str, title: Optional[str] = None, company: Optional[str] = None, location: Optional[str] = None) -> JobPosting:
    # Fetch HTML
    try:
        import requests  # type: ignore
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        # If fetching fails, store URL and minimal text so caller can see error
        text = f"Failed to fetch URL: {url}. Error: {e}"
        return job_from_text(text, title=title, company=company, location=location, keywords=[])

    text = _extract_main_text_from_html(html)
    keywords = extract_keywords(text)
    return job_from_text(text=text, title=title, company=company, location=location, keywords=keywords)


def save_job_text(job: JobPosting, out_path: str) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(job.text or "", encoding="utf-8")
    return str(p)


def load_job_from_url_dynamic(url: str, title: Optional[str] = None, company: Optional[str] = None, location: Optional[str] = None, wait_selector: Optional[str] = None, timeout_ms: int = 15000) -> JobPosting:
    # Render JS via Playwright to get fully-hydrated HTML
    html = ""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=timeout_ms)
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms)
                except Exception:
                    pass
            html = page.content()
            browser.close()
    except Exception as e:
        html = f""
    if not html:
        # Fallback to basic loader
        return load_job_from_url(url, title=title, company=company, location=location)
    text = _extract_main_text_from_html(html)
    keywords = extract_keywords(text)
    return job_from_text(text=text, title=title, company=company, location=location, keywords=keywords)
