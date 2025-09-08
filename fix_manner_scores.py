#!/usr/bin/env python3

import asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

# Database connection
DATABASE_URL = "mysql+pymysql://team_user:team_password_123@localhost:3307/team_project_db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def calculate_manner_score_from_rating(rating: float) -> float:
    """리뷰 별점을 기준으로 매너점수 변화량 계산"""
    if rating >= 4.5:
        return 2.0
    elif rating >= 4.0:
        return 1.5
    elif rating >= 3.5:
        return 1.0
    elif rating >= 3.0:
        return 0.5
    elif rating >= 2.5:
        return 0.0
    elif rating >= 2.0:
        return -0.5
    elif rating >= 1.5:
        return -1.0
    else:
        return -1.5

def update_manner_score(current_score: float, score_change: float) -> float:
    """매너 점수 업데이트 (30-100 범위 유지)"""
    new_score = current_score + score_change
    return max(30.0, min(100.0, new_score))

def main():
    session = Session()
    try:
        # 기존 리뷰들 가져오기
        reviews_query = """
        SELECT r.target_user_id, r.rating 
        FROM reviews r 
        WHERE r.target_user_id IS NOT NULL 
        AND r.status = 'visible'
        ORDER BY r.target_user_id, r.created_at
        """
        
        reviews = session.execute(text(reviews_query)).fetchall()
        
        # 사용자별로 매너점수 계산
        user_scores = {}
        for target_user_id, rating in reviews:
            if target_user_id not in user_scores:
                user_scores[target_user_id] = 30.0  # 기본값
            
            score_change = calculate_manner_score_from_rating(float(rating))
            user_scores[target_user_id] = update_manner_score(user_scores[target_user_id], score_change)
            
        print(f"Processing {len(user_scores)} users...")
        
        # 각 사용자의 매너점수 업데이트
        for user_id, final_score in user_scores.items():
            print(f"User ID {user_id}: Updating manner score to {final_score}")
            update_query = text("UPDATE users SET manner_score = :score WHERE id = :user_id")
            session.execute(update_query, {"score": final_score, "user_id": user_id})
        
        session.commit()
        print("Manner scores updated successfully!")
        
        # 결과 확인
        print("\nUpdated manner scores:")
        result_query = """
        SELECT u.id, u.username, u.name, u.manner_score 
        FROM users u 
        WHERE u.id IN (SELECT DISTINCT r.target_user_id FROM reviews r WHERE r.target_user_id IS NOT NULL)
        ORDER BY u.id
        """
        results = session.execute(text(result_query)).fetchall()
        
        for user_id, username, name, manner_score in results:
            print(f"User ID {user_id} ({username}/{name}): {manner_score}")
            
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()