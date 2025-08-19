# app/services/predictor.py
from __future__ import annotations
from typing import Tuple
import numpy as np
from app.nlp.model_loader import embed_texts
from app.services.store import store

# (선택) 정책상 반드시 매칭시킬 키워드는 여기에; 키는 소문자 비교됨
FORCE_MAP: dict[str, str] = {
    # "롤": "게임/오락",
    # "토익": "외국/언어",
}

# 하이브리드 가중치 (고유명사 매칭 강화)
W_CENTROID = 0.4
W_KEYWORD  = 0.6

# 점수 임계치(너무 낮으면 "기타")
CONFIDENCE_THRESHOLD = 0.30

# 키워드-쿼리 유사도가 매우 높을 때 카테고리 확정
SOFT_OVERRIDE_THRESHOLD = 0.95

def _top1(arr: np.ndarray) -> tuple[int, float]:
    idx = int(arr.argmax())
    return idx, float(arr[idx])

def predict_category(query: str) -> Tuple[str, float]:
    """
    입력 쿼리 → (카테고리, 스코어)
    우선순위:
      0) FORCE_MAP 정확일치
      1) category_keywords.json 정확일치
      2) 임베딩 기반 하이브리드 (센트로이드/키워드)
         + 키워드 유사도 매우 높으면 소프트 오버라이드
    """
    q = (query or "").strip()
    if not q:
        return "기타", 0.0

    low = q.lower()

    # 0) 하드 매핑(정책 강제)
    if low in FORCE_MAP:
        return FORCE_MAP[low], 1.0

    # 1) 카테고리 사전 정확일치
    if low in store.term_to_cat:
        return store.term_to_cat[low], 1.0

    # 2) 임베딩
    q_vec = embed_texts([q])  # (1, d)
    if q_vec.shape[0] == 0 or store.centroids.shape[0] == 0:
        return "기타", 0.0

    # 3) 센트로이드 유사도 (코사인 = 내적)
    c_scores = (q_vec @ store.centroids.T)[0]   # (num_cat,)
    # 4) 키워드별 유사도 → 카테고리별 최대값
    if store.flat_vecs.shape[0] > 0:
        k_scores_all = (q_vec @ store.flat_vecs.T)[0]  # (num_terms,)

        # 카테고리별 최대 + 소프트 오버라이드 후보
        best_by_cat = {cat: 0.0 for cat in store.centroid_labels}
        best_term_score = -1.0
        best_term_label = None

        for s, cat in zip(k_scores_all, store.flat_labels):
            fs = float(s)
            if fs > best_by_cat[cat]:
                best_by_cat[cat] = fs
            if fs > best_term_score:
                best_term_score = fs
                best_term_label = cat

        # 소프트 오버라이드: 특정 키워드와 0.95 이상이면 바로 확정
        if best_term_score >= SOFT_OVERRIDE_THRESHOLD and best_term_label:
            return best_term_label, best_term_score

        k_scores = np.array([best_by_cat[cat] for cat in store.centroid_labels], dtype="float32")
    else:
        k_scores = np.zeros_like(c_scores, dtype="float32")

    # 5) 하이브리드 가중합
    hybrid = W_CENTROID * c_scores + W_KEYWORD * k_scores
    h_idx, h_top = _top1(hybrid)

    tag = store.centroid_labels[h_idx]
    score = float(h_top)

    if score < CONFIDENCE_THRESHOLD:
        return "기타", score
    return tag, score