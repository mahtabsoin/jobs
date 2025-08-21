from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from .docs import read_text_generic, parse_resume_text
from .linkedin_ingest import load_linkedin_profile_json


def _merge_candidate(pieces: List[Dict], source_ids: List[str], prefer_substr: str | None = None) -> Dict:
    # Merge multiple parsed resumes into a consolidated candidate dict
    work_experience = []
    skills_hard = []
    education = []

    def dedup_list(items: List[str]) -> List[str]:
        seen = set()
        out = []
        for x in items:
            k = x.strip().lower()
            if k and k not in seen:
                seen.add(k)
                out.append(x.strip())
        return out

    for piece, sid in zip(pieces, source_ids):
        for exp in piece.get("work_experience", []):
            bullets = [{"text": b, "source_ids": [sid]} for b in exp.get("bullets", [])]
            work_experience.append(
                {
                    "company": exp.get("company", ""),
                    "role": exp.get("role", ""),
                    "start": exp.get("start"),
                    "end": exp.get("end"),
                    "bullets": bullets,
                    "skills": [],
                    "tools": [],
                }
            )
        skills_hard.extend(piece.get("skills", []))
        education.extend(piece.get("education", []))

    # Coalesce duplicate roles by (company, role, start, end)
    merged_roles: Dict[str, Dict] = {}
    for exp in work_experience:
        key = "|".join([exp.get("company", ""), exp.get("role", ""), str(exp.get("start")), str(exp.get("end"))])
        slot = merged_roles.setdefault(key, {**exp, "bullets": []})
        existing_texts = {b["text"].strip().lower() for b in slot["bullets"]}
        for b in exp.get("bullets", []):
            k = b["text"].strip().lower()
            if k and k not in existing_texts:
                slot["bullets"].append(b)
                existing_texts.add(k)

    # Deduplicate education entries by (institution, degree, start, end)
    edu_map: Dict[str, Dict] = {}
    for ed in education:
        key = "|".join(
            [
                (ed.get("institution", "") or "").strip().lower(),
                (ed.get("degree", "") or "").strip().lower(),
                str(ed.get("start", "")),
                str(ed.get("end", "")),
            ]
        )
        if key not in edu_map:
            edu_map[key] = ed

    merged_experience = list(merged_roles.values())
    # If a preference is given, reorder bullets and experiences to prefer that source
    if prefer_substr:
        pref = prefer_substr.lower()
        for exp in merged_experience:
            pref_bullets = [b for b in exp.get("bullets", []) if any(pref in sid.lower() for sid in b.get("source_ids", []))]
            other_bullets = [b for b in exp.get("bullets", []) if b not in pref_bullets]
            exp["bullets"] = pref_bullets + other_bullets
        merged_experience.sort(
            key=lambda e: any(pref in sid.lower() for b in e.get("bullets", []) for sid in b.get("source_ids", [])),
            reverse=True,
        )

    return {
        "identity": {"name": "", "email": "", "phone": "", "location": "", "links": []},
        "work_experience": merged_experience,
        "education": list(edu_map.values()),
        "skills": {"hard": dedup_list(skills_hard), "soft": []},
        "certifications": [],
        "projects": [],
        "artifacts": [{"source_id": sid, "type": "resume_or_letter", "uri_or_text": sid} for sid in source_ids],
    }


def main():
    parser = argparse.ArgumentParser(description="Parse a folder of resumes/letters into candidate JSON")
    parser.add_argument("--input", required=True, help="Folder containing PDF/DOCX/TXT resumes and cover letters")
    parser.add_argument("--out", required=True, help="Output JSON path for candidate profile")
    # Optional identity overrides
    parser.add_argument("--name")
    parser.add_argument("--email")
    parser.add_argument("--phone")
    parser.add_argument("--location")
    parser.add_argument("--links", help="Comma-separated links (LinkedIn, GitHub, etc.)")
    parser.add_argument(
        "--interactive", action="store_true", help="Prompt to confirm identity fields before saving"
    )
    parser.add_argument("--prefer", help="Prefer content from files whose name contains this substring")
    parser.add_argument("--linkedin", help="Path to LinkedIn Profile.json (from your data export)")

    args = parser.parse_args()
    in_dir = Path(args.input)
    files = sorted([p for p in in_dir.rglob("*") if p.suffix.lower() in {".pdf", ".docx", ".txt"}])
    if not files:
        raise SystemExit("No PDF/DOCX/TXT files found in the input folder.")

    pieces: List[Dict] = []
    source_ids: List[str] = []
    for f in files:
        text = read_text_generic(str(f))
        parsed = parse_resume_text(text)
        pieces.append(parsed)
        source_ids.append(f.name)

    # LinkedIn ingest (optional)
    if args.linkedin:
        try:
            li = load_linkedin_profile_json(args.linkedin)
            # Convert into our intermediate shape
            li_piece = {
                "work_experience": [
                    {"company": e.get("company", ""), "role": e.get("role", ""), "start": e.get("start"), "end": e.get("end"), "bullets": []}
                    for e in li.get("work_experience", [])
                ],
                "education": li.get("education", []),
                "skills": li.get("skills", []),
            }
            pieces.append(li_piece)
            source_ids.append("linkedin_profile")
        except Exception:
            pass

    merged = _merge_candidate(pieces, source_ids, prefer_substr=args.prefer)
    # Set identity from flags if provided
    if args.name:
        merged["identity"]["name"] = args.name
    if args.email:
        merged["identity"]["email"] = args.email
    if args.phone:
        merged["identity"]["phone"] = args.phone
    if args.location:
        merged["identity"]["location"] = args.location
    if args.links:
        merged["identity"]["links"] = [s.strip() for s in args.links.split(",") if s.strip()]

    # Optional interactive confirmation of identity
    if args.interactive:
        print("\nConfirm identity fields (Enter to keep current):")
        for key in ["name", "email", "phone", "location"]:
            current = merged["identity"].get(key, "")
            new = input(f"{key.capitalize()} [{current}]: ").strip()
            if new:
                merged["identity"][key] = new
        if not merged["identity"].get("links"):
            ln = input("Links (comma-separated): ").strip()
            if ln:
                merged["identity"]["links"] = [s.strip() for s in ln.split(",") if s.strip()]

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote candidate JSON: {args.out}")


if __name__ == "__main__":
    main()
