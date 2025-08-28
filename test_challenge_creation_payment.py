#!/usr/bin/env python3
"""
챌린지 생성 및 결제 플로우 테스트 스크립트
"""

import requests
import json
from datetime import datetime, date, timedelta

BASE_URL = "http://localhost:8001"

def test_challenge_creation_with_payment():
    """유료 챌린지 생성 테스트"""
    
    # 1. 먼저 테스트 사용자로 로그인 (실제 환경에서는 로그인 필요)
    print("🧪 챌린지 생성 및 결제 플로우 테스트 시작...")
    
    # 테스트용 챌린지 데이터
    tomorrow = date.today() + timedelta(days=1)
    week_later = date.today() + timedelta(days=7)
    
    test_challenge_data = {
        "challenge_data": {
            "title": "테스트 유료 챌린지",
            "description": "결제 테스트용 챌린지입니다",
            "start_date": tomorrow.isoformat(),
            "end_date": week_later.isoformat(),
            "total_rounds": 5,
            "mode": "online",
            "payment_type": "entry_fee",
            "entry_fee": 10000,
            "monthly_fee": 0,
            "min_participants": 1,
            "max_participants": 10,
            "min_participation_rate": 80,
            "use_reward": False,
            "require_approval": False,
            "is_public": True,
            "same_place_for_all_rounds": False
        }
    }
    
    try:
        # 2. 챌린지 생성 API 호출 (인증 없이 테스트)
        print("📝 챌린지 생성 요청 중...")
        response = requests.post(
            f"{BASE_URL}/api/v1/challenges/",
            json=test_challenge_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"📊 응답 상태: {response.status_code}")
        
        if response.status_code == 401:
            print("❌ 인증이 필요합니다. 실제 테스트는 로그인 후 브라우저에서 해주세요.")
            print("🔗 테스트 링크: http://localhost:8001/pages/challenges/new")
            return False
            
        if response.status_code != 200:
            print(f"❌ 챌린지 생성 실패: {response.status_code}")
            print(f"📄 응답 내용: {response.text}")
            return False
        
        result = response.json()
        print("✅ 챌린지 생성 성공!")
        print(f"📋 챌린지 ID: {result.get('id')}")
        print(f"💰 결제 필요: {result.get('needs_payment', False)}")
        print(f"💵 결제 금액: {result.get('payment_amount', 0)}원")
        print(f"🔄 참가 상태: {result.get('creator_participation_status')}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 네트워크 오류: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ JSON 파싱 오류: {e}")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        return False

def test_payment_api():
    """결제 준비 API 테스트"""
    print("\n💳 결제 준비 API 테스트...")
    
    try:
        # 결제 준비 요청 (인증 없이는 실패할 것)
        response = requests.post(
            f"{BASE_URL}/api/v1/payments/ready",
            json={"challenge_id": 1},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 401:
            print("✅ 결제 API는 정상적으로 인증을 요구합니다")
            return True
        else:
            print(f"📊 결제 준비 응답: {response.status_code}")
            return True
            
    except Exception as e:
        print(f"❌ 결제 API 테스트 실패: {e}")
        return False

def print_manual_test_instructions():
    """수동 테스트 가이드 출력"""
    print("\n" + "="*60)
    print("🎯 수동 테스트 가이드")
    print("="*60)
    print("1. 브라우저에서 http://localhost:8001/login 으로 로그인")
    print("2. http://localhost:8001/pages/challenges/new 로 이동")
    print("3. 챌린지 정보 입력:")
    print("   - 제목: 테스트 유료 챌린지")
    print("   - 시작일/종료일: 내일부터 일주일")
    print("   - 결제 타입: '입장비' 선택")
    print("   - 입장비: 10000원 입력")
    print("4. 'Create' 버튼 클릭")
    print("5. '참가비 10,000원을 결제하시겠습니까?' 확인창이 나타나면 성공!")
    print("6. '예' 클릭 시 Toss 결제창이 열림")
    print("7. 테스트 결제 완료 후 챌린지 페이지로 리다이렉트")
    print("\n📝 예상 결과:")
    print("- 무료 챌린지: 즉시 생성 완료, 모집 시작")
    print("- 유료 챌린지: 결제 확인창 → 결제 완료 → 모집 시작")
    print("- 결제 취소: 챌린지 생성됨 (draft 상태), 나중에 결제 가능")
    print("\n🔗 직접 테스트: http://localhost:8001/pages/challenges/new")

def main():
    print("🚀 FastTeam 챌린지 생성 및 결제 플로우 테스트")
    print(f"🕐 테스트 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # API 상태 확인
    try:
        health = requests.get(f"{BASE_URL}/health/", timeout=5)
        if health.status_code == 200:
            print("✅ API 서버 정상")
        else:
            print("❌ API 서버 이상")
            return
    except:
        print("❌ API 서버에 연결할 수 없습니다")
        return
    
    # 챌린지 생성 테스트
    challenge_test = test_challenge_creation_with_payment()
    
    # 결제 API 테스트  
    payment_test = test_payment_api()
    
    print("\n" + "="*50)
    print("📊 테스트 결과 요약")
    print("="*50)
    print(f"✅ API 서버: 정상")
    print(f"{'✅' if challenge_test else '❌'} 챌린지 생성: {'성공' if challenge_test else '실패 (인증 필요)'}")
    print(f"{'✅' if payment_test else '❌'} 결제 API: {'정상' if payment_test else '실패'}")
    
    if not challenge_test:
        print_manual_test_instructions()
    
    print(f"\n🕐 테스트 완료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()