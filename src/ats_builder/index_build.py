from __future__ import annotations

import argparse
import json
from pathlib import Path

from .vectorstore import build_tfidf_index_from_candidate


def main():
    parser = argparse.ArgumentParser(description="Build a local TF-IDF index from candidate JSON")
    parser.add_argument("--candidate", required=True, help="Path to candidate JSON")
    parser.add_argument("--out", required=True, help="Output path for index file (e.g., .index/candidate_index.pkl)")
    args = parser.parse_args()

    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    path = build_tfidf_index_from_candidate(candidate, args.out)
    print(f"Wrote index: {path}")


if __name__ == "__main__":
    main()

