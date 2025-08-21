from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import joblib


@dataclass
class EmbChunk:
    text: str
    meta: Dict


class FAISSStore:
    def __init__(self, chunks: List[EmbChunk]):
        self.chunks = chunks
        self.embeddings = None
        self.index = None
        self.model_name = None

    @staticmethod
    def _embed_texts(texts: List[str], model_name: str):
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as e:
            raise RuntimeError("sentence-transformers not installed") from e
        model = SentenceTransformer(model_name)
        return model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

    def build(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", dedup_threshold: float = 0.9):
        # Embed
        texts = [c.text for c in self.chunks]
        if not texts:
            self.embeddings = None
            self.index = None
            return self
        embs = self._embed_texts(texts, model_name)
        # Deduplicate highly similar chunks
        try:
            import numpy as np  # type: ignore
            from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
        except Exception as e:
            raise RuntimeError("numpy/sklearn not installed for FAISS dedup") from e
        sims = cosine_similarity(embs)
        keep = []
        seen = set()
        for i in range(len(texts)):
            if i in seen:
                continue
            keep.append(i)
            dups = np.where(sims[i] >= dedup_threshold)[0]
            for j in dups:
                seen.add(int(j))
        kept_chunks = [self.chunks[i] for i in keep]
        kept_embs = embs[keep]

        # Build FAISS index
        try:
            import faiss  # type: ignore
        except Exception as e:
            raise RuntimeError("faiss-cpu not installed") from e
        dim = kept_embs.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(kept_embs)

        self.chunks = kept_chunks
        self.embeddings = kept_embs
        self.index = index
        self.model_name = model_name
        return self

    def search(self, query: str, top_k: int = 8) -> List[EmbChunk]:
        if self.index is None:
            return []
        try:
            import numpy as np  # type: ignore
        except Exception:
            return []
        q = self._embed_texts([query], self.model_name)
        D, I = self.index.search(q, top_k)  # type: ignore
        idxs = [int(i) for i in I[0] if i >= 0]
        return [self.chunks[i] for i in idxs]

    def save(self, path: str):
        joblib.dump({
            "chunks": self.chunks,
            "embeddings": self.embeddings,
            "model": self.model_name,
        }, path)

    @staticmethod
    def load(path: str) -> "FAISSStore":
        try:
            import faiss  # type: ignore
        except Exception as e:
            raise RuntimeError("faiss-cpu not installed") from e
        data = joblib.load(path)
        chunks = data["chunks"]
        embs = data["embeddings"]
        model_name = data.get("model", "sentence-transformers/all-MiniLM-L6-v2")
        store = FAISSStore(chunks)
        store.model_name = model_name
        # Rebuild index from saved embeddings
        if embs is not None:
            dim = embs.shape[1]
            index = faiss.IndexFlatIP(dim)
            index.add(embs)
            store.embeddings = embs
            store.index = index
        return store

