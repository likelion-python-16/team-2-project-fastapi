# app/services/smart_tag_matcher.py
from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np
from functools import lru_cache

from app.nlp.model_loader import embed_texts

class SmartTagMatcher:
    """카테고리 키워드와 NLP 모델을 사용한 스마트 태그 매칭"""
    
    def __init__(self):
        self.category_keywords = self._load_category_keywords()
        self.category_embeddings = self._create_category_embeddings()
        
    def _load_category_keywords(self) -> Dict[str, List[str]]:
        """카테고리 키워드 로드"""
        keywords_path = Path("data/category_keywords.json")
        if not keywords_path.exists():
            return {}
            
        with open(keywords_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @lru_cache(maxsize=1)
    def _create_category_embeddings(self) -> Dict[str, np.ndarray]:
        """각 카테고리의 키워드들을 임베딩으로 변환"""
        embeddings = {}
        
        for category, keywords in self.category_keywords.items():
            if not keywords:
                continue
                
            # 키워드들을 임베딩으로 변환
            keyword_embeddings = embed_texts(keywords)
            # 평균 임베딩을 카테고리 대표 임베딩으로 사용
            category_embedding = np.mean(keyword_embeddings, axis=0)
            embeddings[category] = category_embedding
            
        return embeddings
    
    def find_best_categories(self, query_text: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """
        쿼리 텍스트와 가장 유사한 카테고리들을 찾음
        
        Args:
            query_text: 검색 텍스트
            top_k: 반환할 카테고리 수
            
        Returns:
            [(카테고리명, 유사도 점수)] 리스트
        """
        if not query_text.strip() or not self.category_embeddings:
            return []
            
        # 쿼리 임베딩
        query_embedding = embed_texts([query_text])[0]
        
        # 각 카테고리와의 유사도 계산
        similarities = []
        for category, category_embedding in self.category_embeddings.items():
            similarity = np.dot(query_embedding, category_embedding)
            similarities.append((category, float(similarity)))
        
        # 유사도 높은 순으로 정렬
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def find_matching_keywords(self, query_text: str, category: str, threshold: float = 0.5) -> List[str]:
        """
        특정 카테고리 내에서 쿼리와 유사한 키워드들을 찾음
        
        Args:
            query_text: 검색 텍스트
            category: 카테고리명
            threshold: 유사도 임계치
            
        Returns:
            매칭된 키워드 리스트
        """
        if category not in self.category_keywords:
            return []
            
        keywords = self.category_keywords[category]
        if not keywords:
            return []
            
        # 키워드들과 쿼리의 유사도 계산
        query_embedding = embed_texts([query_text])[0]
        keyword_embeddings = embed_texts(keywords)
        
        similarities = np.dot(keyword_embeddings, query_embedding)
        
        # 임계치 이상인 키워드들 반환
        matching_keywords = []
        for i, similarity in enumerate(similarities):
            if similarity >= threshold:
                matching_keywords.append(keywords[i])
                
        return matching_keywords
    
    def get_category_expansion(self, categories: List[str]) -> List[str]:
        """
        카테고리들의 키워드를 모두 가져와서 검색 확장
        
        Args:
            categories: 카테고리 리스트
            
        Returns:
            확장된 키워드 리스트
        """
        expanded_keywords = []
        for category in categories:
            if category in self.category_keywords:
                expanded_keywords.extend(self.category_keywords[category])
        
        return list(set(expanded_keywords))  # 중복 제거

# 글로벌 인스턴스
@lru_cache(maxsize=1)
def get_smart_tag_matcher() -> SmartTagMatcher:
    """싱글톤 SmartTagMatcher 인스턴스 반환"""
    return SmartTagMatcher()