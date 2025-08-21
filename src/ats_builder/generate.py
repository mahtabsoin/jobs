from __future__ import annotations

from typing import Dict, List

from .schemas import Candidate, JobPosting, SelectionResult


def build_resume_context(candidate: Candidate, job: JobPosting, selection: SelectionResult) -> Dict:
    # Build a renderable structure while preserving source trace
    experiences = []
    for idx, exp in enumerate(candidate.work_experience):
        picked = selection.selected_by_role.get(idx, [])
        bullets = [
            {
                "text": sb.text,
                "source_ids": sb.source_ids,
            }
            for sb in picked
        ]
        experiences.append(
            {
                "company": exp.company,
                "role": exp.role,
                "start": exp.start,
                "end": exp.end,
                "bullets": bullets,
            }
        )

    skills = list(dict.fromkeys(candidate.skills_hard + candidate.skills_soft))

    return {
        "identity": {
            "name": candidate.identity.name,
            "email": candidate.identity.email,
            "phone": candidate.identity.phone,
            "location": candidate.identity.location,
            "links": candidate.identity.links,
        },
        "experiences": experiences,
        "education": [
            {
                "institution": ed.institution,
                "degree": ed.degree,
                "start": ed.start,
                "end": ed.end,
            }
            for ed in candidate.education
        ],
        "skills": skills,
        "trace": {
            # Flat bullet trace for transparency
            "bullets": [
                {
                    "text": sb.text,
                    "source_ids": sb.source_ids,
                    "role_index": ridx,
                    "score": sb.score,
                }
                for ridx, lst in selection.selected_by_role.items() for sb in lst
            ]
        },
        "job": {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "keywords": job.keywords,
        },
    }


def build_cover_letter(candidate: Candidate, job: JobPosting, selection: SelectionResult, personal_notes: str | None = None) -> Dict:
    name = candidate.identity.name
    company = job.company or "your team"
    title = job.title or "this role"

    # Collect 2–3 honest highlights from selected bullets
    all_bullets: List[str] = []
    for idx in sorted(selection.selected_by_role.keys()):
        all_bullets.extend([sb.text for sb in selection.selected_by_role[idx]])
    highlights = all_bullets[:3]

    # Build a natural, personal tone with concrete references
    lead_skills = [s for s in candidate.skills_hard][:3]
    soft = [s for s in candidate.skills_soft][:2]
    intro = (
        f"I'm reaching out about the {title} at {company}. "
        f"My recent work has centered on {', '.join(lead_skills)}"
        + (f" and I tend to bring {', '.join(soft)} to cross‑functional work." if soft else ".")
    )

    if highlights:
        middle = (
            "A few examples of the kind of work I do: "
            + "; ".join(highlights)
            + "."
        )
    else:
        middle = "I’m glad to share examples of recent projects on request."

    closing = (
        "If the team is exploring solutions in this area, I’d value a conversation to compare notes and see where I can help."
    )

    if personal_notes:
        middle = middle + " " + personal_notes.strip()

    return {
        "greeting": "Hello,",
        "paragraphs": [intro, middle, closing],
        "closing": f"Best regards,\n{name}",
    }
