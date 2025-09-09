# app/services/store.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List
import numpy as np
from app.nlp.model_loader_dummy import embed_texts

# 카테고리 키워드 사전 경로 (필수)
DATA_PATH = Path("data/category_keywords.json")

class KeywordStore:
    """
    - categories: {카테고리: [키워드들]}
    - centroids:  카테고리별 센트로이드 임베딩 (num_cat, d)
    - centroid_labels: 센트로이드 라벨 순서 (length = num_cat)
    - flat_terms / flat_labels / flat_vecs: 개별 키워드 풀(flat)과 임베딩
    - term_to_cat: 소문자 정규화된 키워드 → 카테고리 역매핑 (정확일치용)
    """
    def __init__(self, path: Path = DATA_PATH):
        self.path = path
        self.categories: Dict[str, List[str]] = {}

        self._centroid_labels: list[str] = []
        self._centroids: np.ndarray = np.empty((0, 384), dtype="float32")

        self._flat_terms: list[str] = []
        self._flat_labels: list[str] = []
        self._flat_vecs: np.ndarray = np.empty((0, 384), dtype="float32")

        self.term_to_cat: dict[str, str] = {}

        self.load()

    def load(self) -> None:
        with open(self.path, "r", encoding="utf-8") as f:
            self.categories = json.load(f)

        labels: list[str] = []
        cents: list[np.ndarray] = []

        flat_terms: list[str] = []
        flat_labels: list[str] = []
        term_to_cat: dict[str, str] = {}

        # 카테고리 순회
        for cat, terms in self.categories.items():
            # 문자열만 남기고 공백 정리
            terms = [t.strip() for t in terms if isinstance(t, str) and t.strip()]
            if not terms:
                continue

            # 역맵 (정확 매칭용, 소문자 키)
            for t in terms:
                term_to_cat[t.lower()] = cat

            # 개별 키워드 임베딩
            vecs = embed_texts(terms)  # (n_i, d)
            # 카테고리 센트로이드
            centroid = vecs.mean(axis=0)
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid = (centroid / norm).astype("float32")
            else:
                centroid = np.zeros((vecs.shape[1],), dtype="float32")

            labels.append(cat)
            cents.append(centroid)

            flat_terms.extend(terms)
            flat_labels.extend([cat] * len(terms))

        self._centroid_labels = labels
        self._centroids = np.vstack(cents) if cents else np.empty((0, 384), dtype="float32")

        self._flat_terms = flat_terms
        self._flat_labels = flat_labels
        self._flat_vecs = embed_texts(flat_terms) if flat_terms else np.empty((0, 384), dtype="float32")

        self.term_to_cat = term_to_cat

    # 노출 프로퍼티
    @property
    def centroid_labels(self) -> list[str]:
        return self._centroid_labels

    @property
    def centroids(self) -> np.ndarray:
        return self._centroids

    @property
    def flat_terms(self) -> list[str]:
        return self._flat_terms

    @property
    def flat_labels(self) -> list[str]:
        return self._flat_labels

    @property
    def flat_vecs(self) -> np.ndarray:
        return self._flat_vecs


# 전역 싱글톤 인스턴스
store = KeywordStore()