#!/usr/bin/env python3
import requests
import json

webhook_url = "https://discord.com/api/webhooks/1413818735537422347/A995lV2ONRQrA8-2yHRSSaqAr6vipKY-AIxBstt4_2uVF669WB7_ojpiQk2UdtMYpYn9"

# 테스트 메시지 전송
payload = {
    "content": "🚀 **Grafana 알림 시스템 테스트**\n\nFastTeam API 모니터링이 연결되었습니다!"
}

try:
    response = requests.post(webhook_url, json=payload)
    if response.status_code == 204:
        print("✅ Discord 메시지 전송 성공!")
    else:
        print(f"❌ 오류: {response.status_code} - {response.text}")
except Exception as e:
    print(f"❌ 연결 오류: {e}")