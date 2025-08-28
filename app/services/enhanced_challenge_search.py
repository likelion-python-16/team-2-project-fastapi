# app/services/enhanced_challenge_search.py
from __future__ import annotations
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from app.models.challenge import Challenge
from app.models.tag import Tag, ChallengeTag
from app.models.participation import Participation
from app.services.smart_tag_matcher import get_smart_tag_matcher

class EnhancedChallengeSearch:
    """스마트 태그 매칭을 사용한 향상된 챌린지 검색"""
    
    def __init__(self, db: Session):
        self.db = db
        self.tag_matcher = get_smart_tag_matcher()
    
    def smart_search(
        self, 
        query: str, 
        limit: int = 20,
        user_id: Optional[int] = None,
        status_filter: str = "recruiting"
    ) -> Dict:
        """
        스마트 태그 매칭을 사용한 챌린지 검색
        
        Returns:
            {
                'direct_matches': 직접 매칭된 챌린지들,
                'tag_based_matches': 태그 기반 매칭된 챌린지들,
                'suggested_categories': 추천 카테고리들,
                'query_analysis': 쿼리 분석 결과
            }
        """
        result = {
            'direct_matches': [],
            'tag_based_matches': [],
            'suggested_categories': [],
            'query_analysis': {}
        }
        
        if not query.strip():
            return result
            
        # 1. 직접 검색 (제목, 설명, 장소 매칭)
        direct_matches = self._direct_text_search(query, limit//2, user_id, status_filter)
        result['direct_matches'] = direct_matches
        
        # 2. AI 기반 카테고리 분석
        best_categories = self.tag_matcher.find_best_categories(query, top_k=3)
        result['suggested_categories'] = best_categories
        result['query_analysis']['matched_categories'] = [cat for cat, score in best_categories if score > 0.3]
        
        # 3. 태그 기반 검색
        if best_categories:
            tag_matches = self._tag_based_search(
                best_categories, 
                limit//2, 
                user_id, 
                status_filter,
                exclude_ids=[ch['id'] for ch in direct_matches]
            )
            result['tag_based_matches'] = tag_matches
            
        # 4. 키워드 확장 분석
        if best_categories:
            top_category = best_categories[0][0]
            matching_keywords = self.tag_matcher.find_matching_keywords(query, top_category, threshold=0.4)
            result['query_analysis']['matching_keywords'] = matching_keywords[:5]
        
        return result
    
    def _direct_text_search(
        self, 
        query: str, 
        limit: int, 
        user_id: Optional[int], 
        status_filter: str
    ) -> List[Dict]:
        """직접 텍스트 검색 (제목, 설명, 장소)"""
        
        like_pattern = f"%{query}%"
        
        # 기본 쿼리
        base_query = self.db.query(Challenge).filter(
            Challenge.is_deleted == False,
            Challenge.status == status_filter,
            or_(
                Challenge.title.ilike(like_pattern),
                Challenge.description.ilike(like_pattern),
                Challenge.default_place_name.ilike(like_pattern),
                Challenge.default_address.ilike(like_pattern)
            )
        )
        
        # 사용자가 이미 참여한 챌린지 제외
        if user_id:
            participated_ids = self.db.query(Participation.challenge_id).filter(
                Participation.user_id == user_id
            ).subquery()
            
            base_query = base_query.filter(
                ~Challenge.id.in_(participated_ids)
            )
        
        challenges = base_query.order_by(Challenge.created_at.desc()).limit(limit).all()
        
        return [self._format_challenge_result(ch, "direct_match") for ch in challenges]
    
    def _tag_based_search(
        self, 
        categories: List[Tuple[str, float]], 
        limit: int, 
        user_id: Optional[int],
        status_filter: str,
        exclude_ids: List[int] = None
    ) -> List[Dict]:
        """태그 기반 챌린지 검색"""
        
        if not categories:
            return []
            
        # 카테고리 이름들 추출
        category_names = [cat for cat, score in categories if score > 0.3]
        
        if not category_names:
            return []
        
        # 해당 카테고리의 태그들 찾기
        matching_tags = self.db.query(Tag).filter(
            Tag.tag.in_(category_names),
            Tag.is_active == True
        ).all()
        
        if not matching_tags:
            return []
        
        tag_ids = [tag.id for tag in matching_tags]
        
        # 태그와 연결된 챌린지들 찾기
        base_query = (
            self.db.query(Challenge)
            .join(ChallengeTag, ChallengeTag.challenge_id == Challenge.id)
            .filter(
                ChallengeTag.tag_id.in_(tag_ids),
                Challenge.is_deleted == False,
                Challenge.status == status_filter
            )
        )
        
        # 이미 매칭된 챌린지들 제외
        if exclude_ids:
            base_query = base_query.filter(~Challenge.id.in_(exclude_ids))
            
        # 사용자가 이미 참여한 챌린지 제외
        if user_id:
            participated_ids = self.db.query(Participation.challenge_id).filter(
                Participation.user_id == user_id
            ).subquery()
            
            base_query = base_query.filter(
                ~Challenge.id.in_(participated_ids)
            )
        
        challenges = base_query.order_by(Challenge.created_at.desc()).limit(limit).all()
        
        return [self._format_challenge_result(ch, "tag_match") for ch in challenges]
    
    def _format_challenge_result(self, challenge: Challenge, match_type: str) -> Dict:
        """챌린지 결과 포맷팅"""
        
        # 참가자 수 계산
        participant_count = self.db.query(Participation).filter(
            Participation.challenge_id == challenge.id,
            Participation.status == 'active'
        ).count()
        
        return {
            'id': challenge.id,
            'title': challenge.title,
            'description': challenge.description,
            'status': challenge.status,
            'mode': challenge.mode,
            'start_date': challenge.start_date.isoformat() if challenge.start_date else None,
            'end_date': challenge.end_date.isoformat() if challenge.end_date else None,
            'default_place_name': challenge.default_place_name,
            'default_address': challenge.default_address,
            'payment_type': challenge.payment_type,
            'entry_fee': challenge.entry_fee,
            'monthly_fee': challenge.monthly_fee,
            'current_participants': participant_count,
            'max_participants': challenge.max_participants,
            'match_type': match_type,
            'created_at': challenge.created_at.isoformat() if challenge.created_at else None
        }

def get_enhanced_challenge_search(db: Session) -> EnhancedChallengeSearch:
    """팩토리 함수"""
    return EnhancedChallengeSearch(db)