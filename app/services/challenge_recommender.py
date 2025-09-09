# app/services/challenge_recommender.py
from __future__ import annotations
import numpy as np
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session
from app.nlp.model_loader_dummy import embed_texts
from app.models.challenge import Challenge
from app.models.participation import Participation
from app.models.user import User
from app.models.tag import UserTag, ChallengeTag, Tag

class ChallengeRecommender:
    """챌린지 기반 추천 시스템"""
    
    def __init__(self, db: Session):
        self.db = db
        
    def find_similar_challenges(
        self, 
        query_text: str, 
        limit: int = 5,
        exclude_challenge_ids: List[int] = None,
        user_id: Optional[int] = None
    ) -> List[Dict]:
        """
        쿼리 텍스트와 유사한 챌린지들을 찾아 추천
        
        Args:
            query_text: 검색할 텍스트 (제목, 설명 등)
            limit: 반환할 추천 챌린지 수
            exclude_challenge_ids: 제외할 챌린지 ID들
            user_id: 사용자 ID (참여한 챌린지 제외용)
        """
        if not query_text.strip():
            return []
            
        exclude_ids = set(exclude_challenge_ids or [])
        
        # 사용자가 이미 참여한 챌린지 제외
        if user_id:
            user_challenges = self.db.query(Participation.challenge_id).filter(
                Participation.user_id == user_id
            ).all()
            exclude_ids.update(ch_id for (ch_id,) in user_challenges)
        
        # 활성 챌린지들 가져오기 (삭제되지 않고, 모집 중인 것들)
        challenges = self.db.query(Challenge).filter(
            Challenge.is_deleted == False,
            Challenge.status.in_(['recruiting', 'active']),
            ~Challenge.id.in_(exclude_ids) if exclude_ids else True
        ).all()
        
        if not challenges:
            return []
            
        return self._rank_challenges_by_similarity(query_text, challenges, limit)
    
    def _rank_challenges_by_similarity(
        self, 
        query_text: str, 
        challenges: List[Challenge], 
        limit: int
    ) -> List[Dict]:
        """챌린지들을 유사도로 랭킹"""
        
        # 쿼리 임베딩
        query_embedding = embed_texts([query_text])[0]  # (384,)
        
        # 챌린지 텍스트들 구성 및 임베딩
        challenge_texts = []
        for ch in challenges:
            # 제목 + 설명을 조합하여 챌린지 텍스트 생성
            title = ch.title or ""
            desc = ch.description or ""
            combined = f"{title} {desc}".strip()
            challenge_texts.append(combined if combined else title or "챌린지")
        
        if not challenge_texts:
            return []
            
        challenge_embeddings = embed_texts(challenge_texts)  # (N, 384)
        
        # 코사인 유사도 계산 (L2 정규화된 벡터들의 내적)
        similarities = np.dot(challenge_embeddings, query_embedding)
        
        # 유사도순으로 정렬
        ranked_indices = np.argsort(similarities)[::-1]
        
        # 상위 N개 선택하고 추가 정보와 함께 반환
        results = []
        for i in ranked_indices[:limit]:
            if similarities[i] < 0.3:  # 최소 유사도 임계치
                break
                
            ch = challenges[i]
            similarity_score = float(similarities[i])
            
            # 참가자 수, 좋아요 수 등 추가 정보
            participant_count = self.db.query(Participation).filter(
                Participation.challenge_id == ch.id,
                Participation.status == 'active'
            ).count()
            
            results.append({
                'challenge': ch,
                'similarity_score': similarity_score,
                'participant_count': participant_count,
                'matched_text': challenge_texts[i][:100] + '...' if len(challenge_texts[i]) > 100 else challenge_texts[i],
                'reasons': self._generate_similarity_reasons(query_text, challenge_texts[i], similarity_score)
            })
        
        return results
    
    def _generate_similarity_reasons(self, query: str, challenge_text: str, score: float) -> List[str]:
        """유사도 이유를 생성"""
        reasons = []
        
        # 점수 기반 이유
        if score > 0.8:
            reasons.append("매우 유사한 내용")
        elif score > 0.6:
            reasons.append("관련성 높음")
        elif score > 0.4:
            reasons.append("일부 관련")
        
        # 키워드 매칭 확인 (간단한 방식)
        query_words = set(query.lower().split())
        challenge_words = set(challenge_text.lower().split())
        common_words = query_words & challenge_words
        
        if len(common_words) > 0:
            reasons.append(f"공통 키워드: {', '.join(list(common_words)[:3])}")
        
        return reasons[:2]  # 최대 2개까지만
    
    def get_trending_challenges(self, limit: int = 10) -> List[Dict]:
        """인기 챌린지 추천 (참가자 수 기반)"""
        challenges = self.db.query(Challenge).filter(
            Challenge.is_deleted == False,
            Challenge.status.in_(['recruiting', 'active'])
        ).order_by(Challenge.current_participants.desc()).limit(limit).all()
        
        results = []
        for ch in challenges:
            participant_count = ch.current_participants or 0
            results.append({
                'challenge': ch,
                'similarity_score': 1.0,  # 인기도 기반이므로 1.0
                'participant_count': participant_count,
                'matched_text': ch.title,
                'reasons': ['인기 챌린지', f'{participant_count}명 참여']
            })
        
        return results
    
    def get_tag_based_recommendations(self, user_id: int, limit: int = 10) -> List[Dict]:
        """
        사용자의 관심 태그를 기반으로 한 챌린지 추천
        사용자가 선택한 태그와 일치하는 챌린지들을 우선 추천
        """
        if not user_id:
            return []
        
        # 사용자가 이미 참여한 챌린지 ID 가져오기
        participated_challenges = set(
            ch_id for (ch_id,) in self.db.query(Participation.challenge_id)
            .filter(Participation.user_id == user_id)
            .all()
        )
        
        # 사용자의 관심 태그 가져오기
        user_tags = self.db.query(UserTag).filter(
            UserTag.user_id == user_id
        ).all()
        
        if not user_tags:
            # 관심 태그가 없으면 인기 챌린지 반환
            return self.get_trending_challenges(limit)
        
        user_tag_ids = [ut.tag_id for ut in user_tags]
        user_tag_names = [ut.tag.tag for ut in user_tags]
        
        # 사용자 관심 태그와 일치하는 챌린지들 찾기 (DB 호환성 개선)
        from sqlalchemy import func, desc
        
        # 1단계: 매칭되는 챌린지와 태그 개수만 먼저 조회
        challenge_matches = self.db.query(
            Challenge,
            func.count(ChallengeTag.id).label('tag_match_count')
        ).join(
            ChallengeTag, Challenge.id == ChallengeTag.challenge_id
        ).filter(
            Challenge.is_deleted == False,
            Challenge.status.in_(['recruiting', 'active']),
            ChallengeTag.tag_id.in_(user_tag_ids),
            ~Challenge.id.in_(participated_challenges) if participated_challenges else True
        ).group_by(
            Challenge.id
        ).order_by(
            desc('tag_match_count'),  # 매칭된 태그 개수로 정렬
            desc(Challenge.current_participants)  # 참가자 수로 2차 정렬
        ).limit(limit).all()
        
        results = []
        for challenge, tag_count in challenge_matches:
            # 2단계: 각 챌린지별로 매칭된 태그들 개별 조회
            matched_tags = self.db.query(Tag.tag).join(
                ChallengeTag, Tag.id == ChallengeTag.tag_id
            ).filter(
                ChallengeTag.challenge_id == challenge.id,
                ChallengeTag.tag_id.in_(user_tag_ids)
            ).all()
            
            matched_tag_names = [tag[0] for tag in matched_tags]
            participant_count = challenge.current_participants or 0
            
            # 매칭 점수 계산 (0.5 ~ 1.0)
            max_possible_matches = min(len(user_tag_names), 5)  # 최대 5개 태그까지만 고려
            similarity_score = 0.5 + (0.5 * tag_count / max_possible_matches)
            
            # 추천 이유 생성
            reasons = []
            if tag_count >= 3:
                reasons.append(f'관심사 {tag_count}개 일치')
            elif tag_count >= 2:
                reasons.append(f'관심사 {tag_count}개 일치')
            else:
                reasons.append('관심사 일치')
            
            # 매칭된 태그들 표시 (최대 3개)
            shown_tags = matched_tag_names[:3]
            if shown_tags:
                reasons.append(f'태그: {", ".join(shown_tags)}')
            
            results.append({
                'challenge': challenge,
                'similarity_score': similarity_score,
                'participant_count': participant_count,
                'matched_text': f"관심사 매칭: {', '.join(shown_tags)}",
                'reasons': reasons,
                'tag_match_count': tag_count,
                'matched_tags': matched_tag_names
            })
        
        # 추천이 부족하면 인기 챌린지로 보완
        if len(results) < limit:
            trending = self.get_trending_challenges(limit - len(results))
            # 중복 제거하면서 추가
            existing_ids = {r['challenge'].id for r in results}
            for trending_item in trending:
                if (trending_item['challenge'].id not in existing_ids and 
                    trending_item['challenge'].id not in participated_challenges):
                    # 태그 매칭이 아닌 것으로 표시
                    trending_item['reasons'] = ['인기 챌린지'] + trending_item['reasons'][1:]
                    trending_item['tag_match_count'] = 0
                    trending_item['matched_tags'] = []
                    results.append(trending_item)
                    if len(results) >= limit:
                        break
        
        return results

def get_challenge_recommender(db: Session) -> ChallengeRecommender:
    """팩토리 함수"""
    return ChallengeRecommender(db)