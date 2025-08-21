from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ingest import load_candidate, load_job, load_job_from_url, save_job_text, load_job_from_url_dynamic
from .match import select_bullets
from .generate import build_resume_context, build_cover_letter
from .render import render_resume, render_cover_letter, try_export_pdf
from .evaluate import summarize_evaluation
from .review import interactive_review
from .llm import refine_resume_ctx_with_llm, generate_cover_letter_with_llm


def main():
    parser = argparse.ArgumentParser(description="ATS-friendly, truthful resume & cover letter builder")
    parser.add_argument("--job", help="Path to job description text file")
    parser.add_argument("--job-url", help="Job posting URL (will be scraped)")
    parser.add_argument("--browser-scrape", action="store_true", help="Use a headless browser (Playwright) to render JS and extract the JD accurately")
    parser.add_argument("--browser-wait", help="CSS selector to wait for before scraping (optional)")
    parser.add_argument("--browser-timeout", type=int, default=15000, help="Playwright navigation/selector timeout in milliseconds")
    parser.add_argument("--candidate", required=True, help="Path to candidate JSON profile")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--title", help="Target role title (optional; overrides detected)")
    parser.add_argument("--company", help="Target company (optional; overrides detected)")
    parser.add_argument("--location", help="Target location (optional)")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF export even if available")
    parser.add_argument("--review", action="store_true", help="Interactive review to refine sections before export")
    parser.add_argument("--notes", help="Path to a text file with personal notes to weave into the cover letter")
    parser.add_argument("--llm", action="store_true", help="Enable LLM refinement (Perplexity)")
    parser.add_argument("--llm-model", default="sonar-reasoning-pro", help="Perplexity model (e.g., sonar-reasoning-pro, sonar-reasoning, sonar)"
    )
    parser.add_argument("--llm-temp", type=float, default=0.4, help="LLM temperature")
    parser.add_argument("--one-page", action="store_true", help="Target one-page resume (tighter bullet budgets)")
    parser.add_argument("--index", help="Path to a saved TF-IDF index (.pkl). If present, will be used to retrieve highlights.")
    parser.add_argument("--build-index", action="store_true", help="If --index is given and does not exist, build it from the candidate JSON.")
    parser.add_argument("--retrieval", choices=["none", "tfidf", "faiss"], default="none", help="Retrieval backend for LLM context")
    parser.add_argument("--faiss", help="Path to a saved FAISS index (.pkl)")
    parser.add_argument("--show-jd", action="store_true", help="Print extracted JD text preview to console")
    parser.add_argument("--jd-save", help="Save extracted JD text to this path (e.g., data/jd_extracted.txt)")
    parser.add_argument("--jd-save-auto", action="store_true", help="Automatically save extracted JD to the output folder with a timestamped filename")
    parser.add_argument("--confirm-jd", action="store_true", help="Ask for confirmation before proceeding with generation")
    parser.add_argument("--prompt-notes", action="store_true", help="Prompt in terminal to add a short personal note if not provided")
    parser.add_argument("--append-datetime", action="store_true", help="Append a timestamp to generated filenames to avoid overwriting")

    args = parser.parse_args()

    candidate = load_candidate(args.candidate)
    if args.job_url:
        if args.browser_scrape:
            job = load_job_from_url_dynamic(
                args.job_url,
                title=args.title,
                company=args.company,
                location=args.location,
                wait_selector=args.browser_wait,
                timeout_ms=args.browser_timeout,
            )
        else:
            job = load_job_from_url(args.job_url, title=args.title, company=args.company, location=args.location)
    elif args.job:
        job = load_job(args.job, title=args.title, company=args.company, location=args.location)
    else:
        raise SystemExit("Please provide either --job or --job-url.")

    # JD preview/save/confirm
    if args.show_jd:
        print("\n--- Extracted Job Description (preview) ---")
        print((job.text or "").strip()[:4000])
        print("\n--- End of preview ---\n")
    if args.jd_save:
        path = save_job_text(job, args.jd_save)
        print(f"Saved extracted JD to: {path}")
    elif args.jd_save_auto:
        # Save under output directory with timestamp
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        auto_path = out_dir / f"jd_extracted_{ts}.txt"
        path = save_job_text(job, str(auto_path))
        print(f"Saved extracted JD to: {path}")
    if args.confirm_jd:
        ans = input("Proceed with this JD? (Y/n): ").strip().lower()
        if ans == "n":
            print("Aborting at your request. You can pass --job <path> with a corrected JD.")
            return

    budgets = (5, 3, 1) if args.one_page else (6, 4, 2)
    selection = select_bullets(candidate, job.keywords, job_text=job.text, budgets=budgets)
    resume_ctx = build_resume_context(candidate, job, selection)

    personal_notes = None
    if args.notes:
        try:
            personal_notes = Path(args.notes).read_text(encoding="utf-8")
        except Exception:
            personal_notes = None
    elif args.prompt_notes:
        print("\nAdd a short personal note for the cover letter (1-3 sentences). Press Enter to skip:")
        typed = input("> ").strip()
        if typed:
            personal_notes = typed
    letter_ctx = build_cover_letter(candidate, job, selection, personal_notes=personal_notes)

    # Optional retrieval: load index to enrich highlights context (for LLM only)
    retrieved_context: list[str] = []
    if args.retrieval == "tfidf" and args.index:
        try:
            from .vectorstore import TfidfStore  # lazy import
            if Path(args.index).exists():
                store = TfidfStore.load(args.index)
            elif args.build_index:
                # Build on the fly from current candidate
                from .vectorstore import build_tfidf_index_from_candidate
                tmp = args.index
                build_tfidf_index_from_candidate(json.loads(Path(args.candidate).read_text(encoding="utf-8")), tmp)
                store = TfidfStore.load(tmp)
            else:
                store = None
            if store:
                hits = store.search(job.text, top_k=8)
                retrieved_context = [h.text for h in hits]
        except Exception:
            retrieved_context = []
    elif args.retrieval == "faiss" and args.faiss:
        try:
            from .faiss_store import FAISSStore  # lazy import
            if Path(args.faiss).exists():
                fstore = FAISSStore.load(args.faiss)
                hits = fstore.search(job.text, top_k=8)
                retrieved_context = [h.text for h in hits]
        except Exception:
            retrieved_context = []

    # Optional LLM refinement (only if API key available and flag enabled)
    if args.llm:
        try:
            resume_ctx = refine_resume_ctx_with_llm(
                resume_ctx, job_keywords=job.keywords, model=args.llm_model, temperature=args.llm_temp
            )
        except Exception:
            pass
        try:
            # Collect highlights from selected bullets after refinement
            hl = []
            for exp in resume_ctx.get("experiences", []):
                hl.extend([b.get("text", "") for b in exp.get("bullets", [])])
            # Add retrieved chunks (dedup)
            seen = set(hl)
            for t in retrieved_context:
                if t not in seen:
                    hl.append(t)
                    seen.add(t)
            llm_letter = generate_cover_letter_with_llm(
                resume_ctx.get("identity", {}), resume_ctx.get("job", {}), hl[:4], personal_notes, model=args.llm_model, temperature=max(args.llm_temp, 0.5)
            )
            if llm_letter:
                letter_ctx = llm_letter
        except Exception:
            pass

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime
    safe_name = candidate.identity.name.replace(" ", "_") or "Candidate"
    safe_role = (args.title or job.title or "Role").replace(" ", "_")
    safe_company = (args.company or job.company or "Company").replace(" ", "_")
    ts_suffix = f"_{datetime.now().strftime('%Y%m%d-%H%M%S')}" if args.append_datetime else ""

    resume_name = f"{safe_name}_{safe_role}_{safe_company}_resume{ts_suffix}.docx"
    letter_name = f"{safe_name}_{safe_role}_{safe_company}_cover_letter{ts_suffix}.docx"

    resume_path = str(out_dir / resume_name)
    cover_letter_path = str(out_dir / letter_name)

    # Evaluation before optional review
    eval_report = summarize_evaluation(resume_ctx.get("job", {}), resume_ctx)
    print("\nEvaluation:")
    print("- Keyword coverage:", eval_report["keyword_coverage"]["coverage"], f"({eval_report['keyword_coverage']['total_keywords']} total keywords)")
    if eval_report["keyword_coverage"]["missing"]:
        print("- Top missing keywords:", ", ".join(eval_report["keyword_coverage"]["missing"]))
    if eval_report["suggestions"]:
        for s in eval_report["suggestions"]:
            print("-", s)

    # Optional interactive review
    if args.review:
        print("\nEntering interactive review. Press Enter to keep defaults; leave blank to skip edits.")
        reviewed = interactive_review(resume_ctx, letter_ctx)
        resume_ctx = reviewed["resume_ctx"]
        letter_ctx = reviewed["letter_ctx"]
        edits = reviewed.get("edits", {})
    else:
        edits = {}

    render_resume(resume_ctx, resume_path)
    render_cover_letter(resume_ctx.get("identity", {}), letter_ctx, job.company, cover_letter_path)

    # Persist a trace for transparency
    trace_path = out_dir / f"{safe_name}_{safe_role}_{safe_company}_trace{ts_suffix}.json"
    trace_payload = {
        "trace": resume_ctx.get("trace", {}),
        "job_keywords": job.keywords,
        "evaluation": eval_report,
        "edits": edits,
    }
    with trace_path.open("w", encoding="utf-8") as f:
        json.dump(trace_payload, f, ensure_ascii=False, indent=2)

    if not args.no_pdf:
        try_export_pdf(resume_path)
        try_export_pdf(cover_letter_path)

    print("Generated:")
    print("-", resume_path)
    print("-", cover_letter_path)
    if not args.no_pdf:
        print("(PDF export attempted when converter available)")


if __name__ == "__main__":
    main()
