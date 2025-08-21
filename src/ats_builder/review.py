from __future__ import annotations

from typing import Dict


def _ask(prompt: str, default: str | None = None) -> str:
    print(prompt)
    if default:
        print(f"[Enter to keep] Current: {default}")
    val = input("> ").strip()
    return default if (not val and default is not None) else val


def interactive_review(resume_ctx: Dict, letter_ctx: Dict) -> Dict:
    edits = {"resume": {"edited": False, "bullets": []}, "letter": {"edited": False}}

    print("\n--- Review: Header ---")
    ident = resume_ctx.get("identity", {})
    ident["name"] = _ask("Name?", ident.get("name", ""))
    ident["email"] = _ask("Email?", ident.get("email", ""))
    ident["phone"] = _ask("Phone?", ident.get("phone", ""))
    ident["location"] = _ask("Location?", ident.get("location", ""))
    resume_ctx["identity"] = ident

    print("\n--- Review: Experience Bullets ---")
    for ri, exp in enumerate(resume_ctx.get("experiences", [])):
        print(f"Role: {exp.get('role','')} | {exp.get('company','')}")
        new_bullets = []
        for bi, b in enumerate(exp.get("bullets", [])):
            print(f"Bullet {bi+1}: {b.get('text','')}")
            choice = _ask("Edit this bullet? (y/N)", "N").lower()
            if choice == "y":
                edited = _ask("Enter revised bullet: ", b.get("text", ""))
                if edited != b.get("text"):
                    edits["resume"]["edited"] = True
                    edits["resume"]["bullets"].append({"role_index": ri, "old": b.get("text"), "new": edited})
                b["text"] = edited
            new_bullets.append(b)
        # Optionally add a new bullet
        add_more = _ask("Add a new bullet to this role? (y/N)", "N").lower()
        if add_more == "y":
            new_text = _ask("New bullet text:", "")
            if new_text:
                edits["resume"]["edited"] = True
                new_bullets.append({"text": new_text, "source_ids": ["user_added"]})
        exp["bullets"] = new_bullets

    print("\n--- Review: Skills ---")
    current_skills = ", ".join(resume_ctx.get("skills", []))
    skills_str = _ask("Skills (comma-separated)?", current_skills)
    resume_ctx["skills"] = [s.strip() for s in skills_str.split(",") if s.strip()]

    print("\n--- Review: Cover Letter ---")
    print("Greeting:", letter_ctx.get("greeting", ""))
    if _ask("Edit greeting? (y/N)", "N").lower() == "y":
        letter_ctx["greeting"] = _ask("New greeting:", letter_ctx.get("greeting", ""))
        edits["letter"]["edited"] = True
    paras = letter_ctx.get("paragraphs", [])
    for i, para in enumerate(paras):
        print(f"Paragraph {i+1}: {para}")
        if _ask("Edit this paragraph? (y/N)", "N").lower() == "y":
            paras[i] = _ask("New text:", para)
            edits["letter"]["edited"] = True
    letter_ctx["paragraphs"] = paras
    print("Closing:", letter_ctx.get("closing", ""))
    if _ask("Edit closing? (y/N)", "N").lower() == "y":
        letter_ctx["closing"] = _ask("New closing:", letter_ctx.get("closing", ""))
        edits["letter"]["edited"] = True

    return {"resume_ctx": resume_ctx, "letter_ctx": letter_ctx, "edits": edits}

