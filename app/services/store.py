# app/services/store.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List
import numpy as np
from app.nlp.model_loader import embed_texts

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

        # AI 임베딩 없이 키워드 매칭만 사용 (메모리 절약)
        term_to_cat: dict[str, str] = {}
        
        for cat, terms in self.categories.items():
            terms = [t.strip() for t in terms if isinstance(t, str) and t.strip()]
            if not terms:
                continue
            
            # 역맵 (정확 매칭용, 소문자 키)
            for t in terms:
                term_to_cat[t.lower()] = cat

        self.term_to_cat = term_to_cat
        
        # AI 관련 속성들은 빈 값으로 초기화
        self._centroid_labels = []
        self._centroids = np.empty((0, 384), dtype="float32")
        self._flat_terms = []
        self._flat_labels = []
        self._flat_vecs = np.empty((0, 384), dtype="float32")

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