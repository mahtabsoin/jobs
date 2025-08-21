from __future__ import annotations

from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from .schemas import Candidate, SelectionResult, SelectedBullet


def _normalize_token(t: str) -> str:
    return t.lower().strip().strip(".,;:!?")


def _token_set(text: str) -> set[str]:
    return { _normalize_token(t) for t in text.split() if t.strip() }


def score_text_against_keywords(text: str, keywords: List[str]) -> float:
    tokens = _token_set(text)
    kws = {_normalize_token(k) for k in keywords}
    if not tokens or not kws:
        return 0.0
    overlap = tokens & kws
    # Jaccard-like score with light length penalty
    base = len(overlap) / max(1, len(kws))
    density = len(overlap) / max(1, len(tokens))
    return base * 0.7 + density * 0.3


def _tfidf_similarity(bullets: List[str], job_text: str) -> List[float]:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
        from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
        docs = [job_text] + bullets
        vectorizer = TfidfVectorizer(min_df=1, ngram_range=(1, 2))
        X = vectorizer.fit_transform(docs)
        sim = cosine_similarity(X[1:], X[0])  # bullets vs JD
        return [float(s[0]) for s in sim]
    except Exception:
        # Fallback: simple token Jaccard vs job text
        jd_tokens = _token_set(job_text)
        out = []
        for b in bullets:
            bt = _token_set(b)
            inter = len(bt & jd_tokens)
            union = len(bt | jd_tokens) or 1
            out.append(inter / union)
        return out


def select_bullets(
    candidate: Candidate,
    keywords: List[str],
    job_text: Optional[str] = None,
    budgets: Tuple[int, int, int] = (6, 4, 2),
) -> SelectionResult:
    selected: Dict[int, List[SelectedBullet]] = defaultdict(list)
    # Recent experience first (assume provided in reverse-chronological; if not, still okay)
    for idx, exp in enumerate(candidate.work_experience):
        scored = []
        bullet_texts = [b.text for b in exp.bullets]
        sim_scores = _tfidf_similarity(bullet_texts, job_text) if (job_text and bullet_texts) else [0.0] * len(bullet_texts)
        for bidx, b in enumerate(exp.bullets):
            kw_score = score_text_against_keywords(b.text, keywords)
            sem = sim_scores[bidx] if bidx < len(sim_scores) else 0.0
            # Blend scores: semantic (0.6) + keyword (0.4). Add tiny boost for role skills overlap.
            s = sem * 0.6 + kw_score * 0.4 + (0.05 * len(set(exp.skills) & set(keywords)))
            if s > 0:
                scored.append(SelectedBullet(role_index=idx, bullet_index=bidx, text=b.text, source_ids=b.source_ids, score=s))
        # Rank bullets and pick a budget based on recency
        scored.sort(key=lambda x: x.score, reverse=True)
        if idx == 0:
            budget = budgets[0]
        elif idx == 1:
            budget = budgets[1]
        else:
            budget = budgets[2]
        selected[idx] = scored[:budget]
    return SelectionResult(selected_by_role=dict(selected), keywords=list(dict.fromkeys(keywords)))
