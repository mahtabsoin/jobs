from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from .docs import read_text_generic, parse_resume_text, normalize_text


def analyze_file(path: Path) -> Dict:
    try:
        raw = read_text_generic(str(path))
    except Exception as e:
        return {"file": path.name, "error": str(e)}
    text = normalize_text(raw)
    lines = [ln for ln in text.splitlines()]
    parsed = parse_resume_text(text)
    exp = parsed.get("work_experience", [])
    bullets = sum(len(e.get("bullets", [])) for e in exp)
    edu = parsed.get("education", [])
    skills = parsed.get("skills", [])
    suggestions: List[str] = []
    if not exp:
        suggestions.append("No Experience section detected — check headings or use DOCX.")
    if bullets == 0 and len(text) < 2000:
        suggestions.append("Very little text — may be a scanned PDF; consider OCR or DOCX export.")
    if not skills:
        suggestions.append("No Skills detected — ensure a clear 'Skills' section or comma-separated list.")

    sample_bullets: List[str] = []
    for e in exp:
        for b in e.get("bullets", []):
            if len(sample_bullets) < 3:
                sample_bullets.append(b)
    return {
        "file": path.name,
        "ext": path.suffix.lower(),
        "chars": len(text),
        "lines": len(lines),
        "experiences": len(exp),
        "bullets": bullets,
        "education": len(edu),
        "skills_count": len(skills),
        "sample_bullets": sample_bullets,
        "suggestions": suggestions,
    }


def main():
    parser = argparse.ArgumentParser(description="Parse report: summarize what was extracted from a documents folder")
    parser.add_argument("--input", required=True, help="Folder containing resumes/letters (PDF/DOCX/TXT)")
    parser.add_argument("--out", help="Optional JSON path to write a detailed report")
    args = parser.parse_args()

    in_dir = Path(args.input)
    files = sorted([p for p in in_dir.rglob("*") if p.suffix.lower() in {".pdf", ".docx", ".txt", ".html", ".htm"}])
    if not files:
        raise SystemExit("No supported files found (PDF/DOCX/TXT/HTML).")

    rows: List[Dict] = []
    for f in files:
        rows.append(analyze_file(f))

    totals = {
        "files": len(rows),
        "total_experiences": sum(r.get("experiences", 0) for r in rows if isinstance(r, dict)),
        "total_bullets": sum(r.get("bullets", 0) for r in rows if isinstance(r, dict)),
        "total_education": sum(r.get("education", 0) for r in rows if isinstance(r, dict)),
    }
    report = {"totals": totals, "files": rows}

    # Print concise console summary
    print(f"Analyzed {totals['files']} files — bullets: {totals['total_bullets']}, experiences: {totals['total_experiences']}, education entries: {totals['total_education']}")
    for r in rows:
        if "error" in r:
            print(f"- {r['file']}: ERROR: {r['error']}")
            continue
        print(f"- {r['file']} | exp={r['experiences']} bullets={r['bullets']} edu={r['education']} skills={r['skills_count']}")
        if r.get("suggestions"):
            print(f"  suggestions: { '; '.join(r['suggestions']) }")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote parse report: {args.out}")


if __name__ == "__main__":
    main()

