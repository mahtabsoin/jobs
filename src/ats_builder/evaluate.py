from __future__ import annotations

from typing import Dict, List


def keyword_coverage(job_keywords: List[str], resume_ctx: Dict) -> Dict:
    # Build a simple token set from selected bullets + skills
    def norm(t: str) -> str:
        return t.lower().strip().strip(".,;:!?()[]{}")

    tokens = set()
    for exp in resume_ctx.get("experiences", []):
        for b in exp.get("bullets", []):
            tokens.update(norm(w) for w in b.get("text", "").split())
    for s in resume_ctx.get("skills", []):
        tokens.add(norm(s))

    kws = [norm(k) for k in job_keywords if k]
    covered = [k for k in kws if k in tokens]
    missing = [k for k in kws if k not in tokens]

    coverage = (len(covered) / max(1, len(kws))) if kws else 0.0
    top_missing = missing[:15]

    return {
        "coverage": round(coverage, 3),
        "covered": covered,
        "missing": top_missing,
        "total_keywords": len(kws),
    }


def summarize_evaluation(job: Dict, resume_ctx: Dict) -> Dict:
    cov = keyword_coverage(job.get("keywords", []), resume_ctx)
    # Simple signals for potential improvements
    suggestions: List[str] = []
    if cov["coverage"] < 0.35:
        suggestions.append("Low keyword coverage; consider adding relevant bullets or skills.")
    if len(resume_ctx.get("experiences", [])) and not any(e.get("bullets") for e in resume_ctx.get("experiences", [])):
        suggestions.append("No bullets selected; ensure candidate bullets are provided.")
    if not resume_ctx.get("skills"):
        suggestions.append("Skills section empty; include key tools and domains from JD.")
    return {"keyword_coverage": cov, "suggestions": suggestions}

