from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


def load_linkedin_profile_json(path: str) -> Dict:
    data = json.loads(Path(path).read_text(encoding="utf-8", errors="ignore"))
    # Some exports wrap content under specific keys; normalize a bit.
    if isinstance(data, dict) and "Profile" in data and isinstance(data["Profile"], dict):
        data = data["Profile"]

    work: List[Dict] = []
    education: List[Dict] = []
    skills: List[str] = []

    # Positions
    positions = data.get("positions") or data.get("Positions") or data.get("experience") or []
    if isinstance(positions, dict) and "values" in positions:
        positions = positions.get("values", [])
    for p in positions or []:
        company = p.get("companyName") or p.get("company") or p.get("organization") or ""
        title = p.get("title") or p.get("positionTitle") or p.get("role") or ""
        start = None
        end = None
        tp = p.get("timePeriod") or p.get("date") or {}
        # Attempt to parse years
        if isinstance(tp, dict):
            start = tp.get("startDate") or tp.get("start")
            end = tp.get("endDate") or tp.get("end")
            if isinstance(start, dict):
                start = start.get("year")
            if isinstance(end, dict):
                end = end.get("year")
        work.append({"company": str(company), "role": str(title), "start": str(start) if start else None, "end": str(end) if end else None, "bullets": []})

    # Education
    edus = data.get("education") or data.get("Education") or []
    if isinstance(edus, dict) and "values" in edus:
        edus = edus.get("values", [])
    for e in edus or []:
        institution = e.get("schoolName") or e.get("organization") or e.get("name") or ""
        degree = e.get("degreeName") or e.get("degree")
        start = e.get("startYear") or (e.get("timePeriod", {}).get("startDate", {}).get("year") if isinstance(e.get("timePeriod"), dict) else None)
        end = e.get("endYear") or (e.get("timePeriod", {}).get("endDate", {}).get("year") if isinstance(e.get("timePeriod"), dict) else None)
        education.append({"institution": str(institution), "degree": str(degree) if degree else None, "start": str(start) if start else None, "end": str(end) if end else None})

    # Skills
    sk = data.get("skills") or data.get("Skills") or []
    if isinstance(sk, dict) and "values" in sk:
        sk = sk.get("values", [])
    for s in sk or []:
        if isinstance(s, dict):
            name = s.get("name") or s.get("skillName")
            if name:
                skills.append(str(name))
        elif isinstance(s, str):
            skills.append(s)

    return {
        "work_experience": work,
        "education": education,
        "skills": skills,
    }

