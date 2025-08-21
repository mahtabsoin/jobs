from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import joblib


@dataclass
class Chunk:
    text: str
    meta: Dict


class TfidfStore:
    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks
        self.vectorizer = None
        self.matrix = None

    def build(self):
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
        texts = [c.text for c in self.chunks]
        self.vectorizer = TfidfVectorizer(min_df=1, ngram_range=(1, 2))
        self.matrix = self.vectorizer.fit_transform(texts)
        return self

    def search(self, query: str, top_k: int = 8) -> List[Chunk]:
        from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
        if not self.vectorizer or self.matrix is None:
            return []
        q = self.vectorizer.transform([query])
        sims = cosine_similarity(self.matrix, q).ravel()
        idxs = sims.argsort()[::-1][:top_k]
        return [self.chunks[i] for i in idxs]

    def save(self, path: str):
        joblib.dump({"chunks": self.chunks, "vectorizer": self.vectorizer, "matrix": self.matrix}, path)

    @staticmethod
    def load(path: str) -> "TfidfStore":
        data = joblib.load(path)
        obj = TfidfStore(data["chunks"])  # type: ignore
        obj.vectorizer = data["vectorizer"]
        obj.matrix = data["matrix"]
        return obj


def build_chunks_from_candidate(candidate: Dict) -> List[Chunk]:
    chunks: List[Chunk] = []
    # Use bullets as chunks; include role/company meta
    for ridx, exp in enumerate(candidate.get("work_experience", [])):
        company = exp.get("company", "")
        role = exp.get("role", "")
        for b in exp.get("bullets", []):
            chunks.append(Chunk(text=b.get("text", ""), meta={"role": role, "company": company, "role_index": ridx, "source_ids": b.get("source_ids", [])}))
    # Optionally add skills and education lines
    for s in candidate.get("skills", {}).get("hard", []):
        chunks.append(Chunk(text=s, meta={"type": "skill"}))
    return chunks


def build_tfidf_index_from_candidate(candidate: Dict, out_path: str) -> str:
    chunks = build_chunks_from_candidate(candidate)
    store = TfidfStore(chunks).build()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    store.save(out_path)
    return out_path

