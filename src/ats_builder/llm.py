from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

import requests


PPLX_API_URL = "https://api.perplexity.ai/chat/completions"


def _env_api_key() -> Optional[str]:
    return os.environ.get("PERPLEXITY_API_KEY") or os.environ.get("PPLX_API_KEY")


def call_perplexity(messages: List[Dict[str, str]], model: str = "sonar-reasoning-pro", temperature: float = 0.2, max_tokens: int = 800) -> Optional[str]:
    api_key = _env_api_key()
    if not api_key:
        return None
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        resp = requests.post(
            PPLX_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        # Perplexity returns OpenAI-like structure
        return data.get("choices", [{}])[0].get("message", {}).get("content")
    except Exception:
        return None


def _digits_set(text: str) -> set[str]:
    return set(re.findall(r"\b\d+(?:[\.,]\d+)?\b", text or ""))


def _safe_rewrite_bullets(originals_by_role: Dict[int, List[str]], job_keywords: List[str], model: str, temperature: float) -> Dict[int, List[str]]:
    # Build prompt
    roles_payload = []
    for ridx, bullets in originals_by_role.items():
        roles_payload.append({"role_index": ridx, "bullets": bullets})
    sys = (
        "You are refining resume bullets for ATS and human readability. "
        "Strict rules: Do not invent facts, employers, titles, dates, or numbers. "
        "Only paraphrase each bullet you are given, keeping all original facts intact. "
        "Keep bullets concise (max ~28 words), action-first, and remove fluff. "
        "Use US spelling. No first-person. No emojis."
    )
    usr = (
        "Job keywords: " + ", ".join(job_keywords[:40]) + "\n\n"
        "Rewrite the bullets with light improvements and natural phrasing. "
        "Return JSON strictly in the schema: {\n"
        "  \"roles\": [ { \"role_index\": int, \"bullets\": [string, ...] }, ... ]\n"
        "}\n"
        "Keep the same number of bullets per role as input.\n\n"
        "Input bullets by role (JSON):\n" + json.dumps({"roles": roles_payload}, ensure_ascii=False)
    )

    content = call_perplexity(
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": usr}],
        model=model,
        temperature=temperature,
        max_tokens=1200,
    )
    if not content:
        return originals_by_role
    # Parse JSON from response content
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        obj = json.loads(content[start:end])
        out: Dict[int, List[str]] = {}
        for role in obj.get("roles", []):
            ridx = int(role.get("role_index"))
            out[ridx] = [str(b) for b in role.get("bullets", [])]
        # Guardrails: numbers must not introduce new digits
        safe: Dict[int, List[str]] = {}
        for ridx, new_bullets in out.items():
            safe_list: List[str] = []
            originals = originals_by_role.get(ridx, [])
            for i, nb in enumerate(new_bullets):
                ob = originals[i] if i < len(originals) else ""
                if not ob:
                    safe_list.append(nb)
                    continue
                new_digits = _digits_set(nb)
                old_digits = _digits_set(ob)
                if new_digits - old_digits:
                    safe_list.append(ob)  # revert to original if new numbers appear
                else:
                    safe_list.append(nb)
            safe[ridx] = safe_list
        return safe
    except Exception:
        return originals_by_role


def refine_resume_ctx_with_llm(resume_ctx: Dict, job_keywords: List[str], model: str = "sonar-reasoning-pro", temperature: float = 0.2) -> Dict:
    # Collect bullets per role
    originals_by_role: Dict[int, List[str]] = {}
    for ridx, exp in enumerate(resume_ctx.get("experiences", [])):
        originals_by_role[ridx] = [b.get("text", "") for b in exp.get("bullets", [])]
    refined_by_role = _safe_rewrite_bullets(originals_by_role, job_keywords, model, temperature)
    # Write back
    for ridx, exp in enumerate(resume_ctx.get("experiences", [])):
        for i, b in enumerate(exp.get("bullets", [])):
            if ridx in refined_by_role and i < len(refined_by_role[ridx]):
                b["text"] = refined_by_role[ridx][i]
                # add a note in trace? we keep source_ids, so okay
    return resume_ctx


def generate_cover_letter_with_llm(identity: Dict, job: Dict, highlights: List[str], personal_notes: Optional[str], model: str = "sonar-reasoning-pro", temperature: float = 0.5) -> Optional[Dict]:
    sys = (
        "Draft a concise, human-sounding cover letter in 3 short paragraphs. "
        "Tone: natural, specific, confident but not salesy. No first-person plural. "
        "Use only the provided highlights; do not invent metrics or new facts."
    )
    usr_payload = {
        "candidate": {k: v for k, v in identity.items() if k in ("name", "location", "links")},
        "job": {k: job.get(k) for k in ("title", "company", "location")},
        "highlights": highlights[:4],
        "personal_notes": personal_notes or "",
    }
    usr = (
        "Write the letter and return JSON with keys: greeting, paragraphs (list of 3), closing.\n" + json.dumps(usr_payload, ensure_ascii=False)
    )
    content = call_perplexity(
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": usr}],
        model=model,
        temperature=temperature,
        max_tokens=800,
    )
    if not content:
        return None
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        obj = json.loads(content[start:end])
        # light validation
        paragraphs = obj.get("paragraphs", [])
        if not isinstance(paragraphs, list) or len(paragraphs) == 0:
            return None
        return {
            "greeting": obj.get("greeting", "Hello,"),
            "paragraphs": paragraphs[:3],
            "closing": obj.get("closing", f"Best regards,\n{identity.get('name','')}"),
        }
    except Exception:
        return None

