# app/nlp/model_loader.py
from __future__ import annotations
from functools import lru_cache
import os
import numpy as np
from sentence_transformers import SentenceTransformer

# HuggingFace/Sentence-Transformers cache directory (container-friendly)
os.environ.setdefault("HF_HOME", "/app/.cache")
os.environ.setdefault("TRANSFORMERS_CACHE", "/app/.cache")
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/app/.cache")
os.environ.setdefault("XDG_CACHE_HOME", "/app/.cache")

# 멀티언어 짧은 쿼리/고유명사에 강한 베이스
MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    # 최초 1회만 다운로드 → 이후 ~/.cache/huggingface 캐시 사용
    return SentenceTransformer(MODEL_ID)

def embed_texts(texts: list[str]) -> np.ndarray:
    """
    입력: 텍스트 리스트
    출력: L2 정규화된 임베딩 (N, 384) float32
    """
    if not texts:
        return np.empty((0, 384), dtype="float32")
    model = get_model()
    vecs = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    # vecs는 이미 L2 정규화됨 → 코사인유사도 = 내적
    return vecs.astype("float32", copy=False)
