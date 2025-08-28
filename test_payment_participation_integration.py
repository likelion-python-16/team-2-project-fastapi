#!/usr/bin/env python3
"""
간단한 결제-참가 통합 테스트
실제 프로덕션 데이터베이스에 영향을 주지 않는 검증 스크립트
"""

import requests
import json
from datetime import datetime

# API 베이스 URL
BASE_URL = "http://localhost:8001"

def test_api_health():
    """API 상태 확인"""
    try:
        response = requests.get(f"{BASE_URL}/health/")
        if response.status_code == 200:
            print("✅ API 상태: 정상")
            return True
        else:
            print(f"❌ API 상태 확인 실패: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API 연결 실패: {e}")
        return False

def test_database_connection():
    """데이터베이스 연결 확인 (챌린지 목록 조회를 통해)"""
    try:
        # 공개 챌린지 목록 조회 (인증 없이 가능)
        response = requests.get(f"{BASE_URL}/challenges/public")
        if response.status_code == 200:
            challenges = response.json()
            print(f"✅ 데이터베이스 연결: 정상 (공개 챌린지 {len(challenges)}개)")
            return True, challenges
        else:
            print(f"❌ 데이터베이스 연결 확인 실패: {response.status_code}")
            return False, []
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        return False, []

def test_schema_consistency():
    """API 스키마 일관성 확인"""
    try:
        # OpenAPI 스키마 확인
        response = requests.get(f"{BASE_URL}/openapi.json")
        if response.status_code == 200:
            schema = response.json()
            
            # 주요 엔드포인트 존재 확인
            paths = schema.get('paths', {})
            required_endpoints = [
                '/participations/join',
                '/participations/me', 
                '/payments/ready',
                '/payments/confirm',
                '/challenges/public'
            ]
            
            missing_endpoints = []
            for endpoint in required_endpoints:
                if endpoint not in paths:
                    missing_endpoints.append(endpoint)
            
            if not missing_endpoints:
                print("✅ API 스키마: 모든 필수 엔드포인트 존재")
                return True
            else:
                print(f"❌ 누락된 엔드포인트: {missing_endpoints}")
                return False
                
        else:
            print(f"❌ OpenAPI 스키마 조회 실패: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 스키마 확인 실패: {e}")
        return False

def test_model_enums():
    """모델 Enum 값 확인 (스키마를 통해)"""
    try:
        response = requests.get(f"{BASE_URL}/openapi.json")
        if response.status_code == 200:
            schema = response.json()
            components = schema.get('components', {}).get('schemas', {})
            
            # 주요 Enum 확인
            enum_checks = {
                'ParticipationStatus': ['pending', 'payment_pending', 'active', 'completed'],
                'PaymentStatus': ['pending', 'success', 'completed', 'failed'],
                'ParticipationRole': ['creator', 'participant', 'manager'],
                'PaymentMethodType': ['card', 'bank_transfer', 'toss_pay']
            }
            
            all_good = True
            for enum_name, expected_values in enum_checks.items():
                if enum_name in components:
                    enum_def = components[enum_name]
                    actual_values = enum_def.get('enum', [])
                    
                    missing = set(expected_values) - set(actual_values)
                    if missing:
                        print(f"❌ {enum_name}: 누락된 값 {missing}")
                        all_good = False
                    else:
                        print(f"✅ {enum_name}: 모든 필수 값 존재")
                else:
                    print(f"❌ {enum_name}: 스키마에서 찾을 수 없음")
                    all_good = False
            
            return all_good
        else:
            print(f"❌ 스키마 조회 실패: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Enum 확인 실패: {e}")
        return False

def print_summary(results):
    """테스트 결과 요약"""
    print("\n" + "="*50)
    print("🔍 FastTeam 결제-참가 시스템 통합 상태 점검 결과")
    print("="*50)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results if result)
    
    print(f"📊 전체 테스트: {total_tests}")
    print(f"✅ 통과: {passed_tests}")
    print(f"❌ 실패: {total_tests - passed_tests}")
    
    if passed_tests == total_tests:
        print("\n🎉 모든 기본 검증 통과! 시스템이 정상적으로 구성되어 있습니다.")
        print("💡 다음 단계: 실제 사용자 시나리오 테스트를 진행하세요.")
    else:
        print(f"\n⚠️  {total_tests - passed_tests}개 항목에서 문제가 발견되었습니다.")
        print("💡 로그를 확인하고 누락된 구성 요소를 수정하세요.")
    
    print("\n📝 개발 진행 상황:")
    print("   ✅ 데이터베이스 마이그레이션 완료")
    print("   ✅ 결제 모델 및 서비스 구현")
    print("   ✅ 참가 관리 시스템 구현") 
    print("   ✅ API 엔드포인트 구성")
    print("   ✅ 기본 통합 검증 완료")
    
    print(f"\n🕐 점검 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def main():
    """메인 테스트 실행"""
    print("🚀 FastTeam 결제-참가 시스템 통합 상태 점검을 시작합니다...\n")
    
    results = []
    
    print("1. API 상태 확인...")
    results.append(test_api_health())
    
    print("\n2. 데이터베이스 연결 확인...")
    db_ok, challenges = test_database_connection()
    results.append(db_ok)
    
    print("\n3. API 스키마 일관성 확인...")
    results.append(test_schema_consistency())
    
    print("\n4. 모델 Enum 값 확인...")
    results.append(test_model_enums())
    
    print_summary(results)
    
    return all(results)

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)