from __future__ import annotations

import argparse
import json
from pathlib import Path

from .faiss_store import FAISSStore, EmbChunk


def chunks_from_candidate(candidate: dict) -> list[EmbChunk]:
    chunks: list[EmbChunk] = []
    for ridx, exp in enumerate(candidate.get("work_experience", [])):
        for b in exp.get("bullets", []):
            chunks.append(EmbChunk(text=b.get("text", ""), meta={"role_index": ridx, "role": exp.get("role", ""), "company": exp.get("company", ""), "source_ids": b.get("source_ids", [])}))
    for s in candidate.get("skills", {}).get("hard", []):
        chunks.append(EmbChunk(text=s, meta={"type": "skill"}))
    return chunks


def main():
    parser = argparse.ArgumentParser(description="Build a FAISS index from candidate JSON")
    parser.add_argument("--candidate", required=True, help="Path to candidate JSON")
    parser.add_argument("--out", required=True, help="Output path (e.g., .index/candidate.faiss.pkl)")
    parser.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2", help="Sentence-transformers model name")
    args = parser.parse_args()

    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    store = FAISSStore(chunks_from_candidate(candidate)).build(model_name=args.model)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    store.save(args.out)
    print(f"Wrote FAISS index: {args.out}")


if __name__ == "__main__":
    main()

