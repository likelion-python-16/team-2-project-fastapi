#!/usr/bin/env python3
"""
월회비 알림 수동 테스트용 스크립트
"""
import requests
from datetime import date, timedelta

def test_monthly_reminder_for_user():
    """특정 사용자의 월회비 알림 테스트"""
    
    print("🔔 월회비 알림 테스트")
    print("=" * 50)
    
    # 1. 챌린지 8번이 월회비 타입인지 확인
    print("\n1. 챌린지 정보 확인...")
    try:
        response = requests.get("http://localhost:8001/api/v1/challenges/8")
        if response.status_code == 200:
            challenge = response.json()
            print(f"✅ 챌린지: {challenge['title']}")
            print(f"   payment_type: {challenge['payment_type']}")
            print(f"   monthly_fee: {challenge['monthly_fee']}원")
            
            if challenge['payment_type'] in ['monthly_fee', 'both'] and challenge['monthly_fee'] > 0:
                print("✅ 월회비 챌린지 확인됨!")
            else:
                print("❌ 월회비 챌린지가 아닙니다.")
                return
        else:
            print(f"❌ 챌린지 조회 실패: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 오류: {e}")
        return
    
    # 2. 월회비 알림 시스템 수동 실행
    print("\n2. 월회비 알림 시스템 실행...")
    print("⚠️ 관리자 권한이 필요합니다.")
    
    token = input("관리자 토큰을 입력하세요 (Enter로 건너뛰기): ").strip()
    
    if token:
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.post(
                "http://localhost:8001/api/v1/payment-reminders/check",
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 알림 시스템 실행 성공: {result}")
            else:
                print(f"❌ 실패: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ 오류: {e}")
    else:
        print("⚠️ 토큰 없이 건너뜀")
    
    # 3. 수동 데이터베이스 설정 방법 안내
    print("\n3. 수동 설정 방법 (DB 직접 접근)")
    print("-" * 30)
    print("""
월회비 알림을 받으려면 다음 SQL을 실행하세요:

-- 내일 결제 예정으로 설정 (1일 전 알림)
UPDATE participations 
SET next_payment_date = DATE_ADD(CURDATE(), INTERVAL 1 DAY),
    payment_cycle = 'monthly'
WHERE challenge_id = 8 AND user_id = [당신의 사용자 ID];

-- 또는 3일 후 결제 예정으로 설정 (3일 전 알림)  
UPDATE participations 
SET next_payment_date = DATE_ADD(CURDATE(), INTERVAL 3 DAY),
    payment_cycle = 'monthly'
WHERE challenge_id = 8 AND user_id = [당신의 사용자 ID];

-- 연체 테스트 (연체 알림)
UPDATE participations 
SET next_payment_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY),
    payment_cycle = 'monthly'
WHERE challenge_id = 8 AND user_id = [당신의 사용자 ID];
""")

    print("\n4. 확인 방법")
    print("-" * 15)
    print("1. 위 SQL 실행 후")
    print("2. 월회비 알림 시스템 수동 실행 (관리자 권한)")  
    print("3. 마이페이지에서 알림 확인")

if __name__ == "__main__":
    test_monthly_reminder_for_user()