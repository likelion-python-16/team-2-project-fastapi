#!/usr/bin/env python3
"""
월회비 알림 시스템 테스트 스크립트
"""
import requests
import json
from datetime import date, timedelta

# 서버 설정
BASE_URL = "http://localhost:8001"

def test_payment_reminders():
    """월회비 알림 시스템 수동 테스트"""
    print("🔔 월회비 알림 시스템 테스트")
    print("=" * 50)
    
    # 관리자 권한이 필요하므로 토큰 필요
    token = input("관리자 토큰을 입력하세요 (없으면 Enter): ").strip()
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        # 1. 수동 알림 실행 테스트
        print("\n1. 수동 알림 실행 테스트...")
        response = requests.post(
            f"{BASE_URL}/api/v1/payment-reminders/check",
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 성공: {result}")
        else:
            print(f"❌ 실패: {response.status_code} - {response.text}")
    
    except requests.exceptions.RequestException as e:
        print(f"❌ 요청 오류: {e}")
    
    try:
        # 2. 다가오는 결제 일정 조회 (로그인 필요)
        print("\n2. 다가오는 결제 일정 조회...")
        if token:
            response = requests.get(
                f"{BASE_URL}/api/v1/payment-reminders/next-payments",
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 다가오는 결제: {json.dumps(result, indent=2, ensure_ascii=False)}")
            else:
                print(f"❌ 실패: {response.status_code} - {response.text}")
        else:
            print("⚠️ 토큰이 없어서 건너뜁니다.")
    
    except requests.exceptions.RequestException as e:
        print(f"❌ 요청 오류: {e}")

def explain_system():
    """월회비 알림 시스템 동작 방식 설명"""
    print("\n📋 월회비 알림 시스템 동작 방식")
    print("=" * 50)
    print("""
🔄 자동 실행 방식:
   - 현재는 수동 실행만 가능
   - 운영 시에는 cron job으로 매일 실행 권장
   
📅 알림 스케줄:
   - 3일 전: "3일 후 월회비 결제 예정 📅"
   - 1일 전: "내일 월회비 결제 예정 📅"
   - 연체 시: "월회비 연체 알림 (1/3) ⚠️"
   
⚠️ 연체 처리:
   - 결제일 + 3일 후부터 연체 처리
   - 3회 연속 실패 시 자동 탈퇴
   - 실패 시마다 7일 유예 기간 연장
   
💾 알림 저장:
   - notifications 테이블에 저장
   - 중복 알림 방지 로직 포함
   
🔧 수동 실행 방법:
   1. POST /api/v1/payment-reminders/check (관리자 권한)
   2. 또는 이 스크립트 실행
   
📱 알림 확인:
   - 마이페이지 알림 목록에서 확인 가능
   - 실시간 알림은 별도 구현 필요
    """)
    
    print("\n🛠️ 월회비 참가자 생성 방법:")
    print("1. 챌린지 생성 시 payment_type을 'monthly_fee'로 설정")
    print("2. monthly_fee 값을 0보다 크게 설정")
    print("3. 사용자가 참여하면 자동으로 next_payment_date 설정됨")
    
    print("\n⏰ cron 설정 예시:")
    print("# 매일 오전 9시에 실행")
    print("0 9 * * * curl -X POST http://localhost:8001/api/v1/payment-reminders/check")

def create_test_data():
    """테스트 데이터 생성 가이드"""
    print("\n🧪 테스트 데이터 생성 방법")
    print("=" * 50)
    print("""
1. 월회비 챌린지 생성:
   - payment_type: "monthly_fee"
   - monthly_fee: 1000 (또는 원하는 금액)
   
2. 테스트 참가자 생성:
   - 월회비 챌린지에 참여
   - next_payment_date를 수동으로 조정:
     
   SQL 예시:
   UPDATE participations 
   SET next_payment_date = CURRENT_DATE + 1  -- 1일 후
   WHERE payment_cycle = 'monthly' AND challenge_id = 챌린지ID;
   
   또는
   UPDATE participations 
   SET next_payment_date = CURRENT_DATE - 3  -- 3일 전 (연체 테스트)
   WHERE payment_cycle = 'monthly' AND challenge_id = 챌린지ID;

3. 알림 테스트:
   - 위 스크립트로 수동 실행
   - notifications 테이블에서 결과 확인
    """)

if __name__ == "__main__":
    print("🔔 월회비 알림 시스템 테스트 도구")
    print("=" * 50)
    
    while True:
        print("\n선택하세요:")
        print("1. 시스템 동작 방식 설명")
        print("2. 수동 알림 테스트 실행")
        print("3. 테스트 데이터 생성 방법")
        print("4. 종료")
        
        choice = input("\n번호를 입력하세요: ").strip()
        
        if choice == "1":
            explain_system()
        elif choice == "2":
            test_payment_reminders()
        elif choice == "3":
            create_test_data()
        elif choice == "4":
            print("종료합니다.")
            break
        else:
            print("잘못된 선택입니다.")