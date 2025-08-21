from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class Identity:
    name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    links: List[str] = field(default_factory=list)


@dataclass
class Artifact:
    source_id: str
    type: str  # e.g., "resume", "linkedin", "note"
    uri_or_text: str


@dataclass
class Bullet:
    text: str
    source_ids: List[str] = field(default_factory=list)


@dataclass
class Experience:
    company: str
    role: str
    start: Optional[str] = None
    end: Optional[str] = None
    bullets: List[Bullet] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)


@dataclass
class Education:
    institution: str
    degree: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None


@dataclass
class Candidate:
    identity: Identity
    work_experience: List[Experience] = field(default_factory=list)
    education: List[Education] = field(default_factory=list)
    skills_hard: List[str] = field(default_factory=list)
    skills_soft: List[str] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    projects: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Artifact] = field(default_factory=list)


@dataclass
class JobPosting:
    text: str
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    keywords: List[str] = field(default_factory=list)


@dataclass
class SelectedBullet:
    role_index: int
    bullet_index: int
    text: str
    source_ids: List[str]
    score: float


@dataclass
class SelectionResult:
    selected_by_role: Dict[int, List[SelectedBullet]] = field(default_factory=dict)
    keywords: List[str] = field(default_factory=list)


@dataclass
class RenderContext:
    candidate: Candidate
    job: JobPosting
    selection: SelectionResult
    target_role: Optional[str] = None
    target_company: Optional[str] = None
    target_location: Optional[str] = None


def _get(d: Dict[str, Any], key: str, default):
    v = d.get(key, default)
    return v if v is not None else default


def candidate_from_dict(data: Dict[str, Any]) -> Candidate:
    ident_d = data.get("identity", {})
    identity = Identity(
        name=ident_d.get("name", ""),
        email=ident_d.get("email", ""),
        phone=ident_d.get("phone"),
        location=ident_d.get("location"),
        links=_get(ident_d, "links", []),
    )

    exps: List[Experience] = []
    for e in _get(data, "work_experience", []):
        bullets = [Bullet(text=b.get("text", ""), source_ids=_get(b, "source_ids", [])) for b in _get(e, "bullets", [])]
        exps.append(
            Experience(
                company=e.get("company", ""),
                role=e.get("role", ""),
                start=e.get("start"),
                end=e.get("end"),
                bullets=bullets,
                skills=_get(e, "skills", []),
                tools=_get(e, "tools", []),
            )
        )

    edus: List[Education] = []
    for ed in _get(data, "education", []):
        edus.append(
            Education(
                institution=ed.get("institution", ""),
                degree=ed.get("degree"),
                start=ed.get("start"),
                end=ed.get("end"),
            )
        )

    artifacts: List[Artifact] = []
    for ar in _get(data, "artifacts", []):
        if "source_id" in ar and "type" in ar and "uri_or_text" in ar:
            artifacts.append(Artifact(source_id=ar["source_id"], type=ar["type"], uri_or_text=ar["uri_or_text"]))

    return Candidate(
        identity=identity,
        work_experience=exps,
        education=edus,
        skills_hard=_get(data, "skills", {}).get("hard", []),
        skills_soft=_get(data, "skills", {}).get("soft", []),
        certifications=_get(data, "certifications", []),
        projects=_get(data, "projects", []),
        artifacts=artifacts,
    )


def job_from_text(text: str, title: Optional[str] = None, company: Optional[str] = None, location: Optional[str] = None, keywords: Optional[List[str]] = None) -> JobPosting:
    return JobPosting(text=text, title=title, company=company, location=location, keywords=keywords or [])

