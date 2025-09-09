#!/usr/bin/env python3
"""
테스트용 웹훅 서버
Grafana 알림을 받아서 콘솔에 출력
"""
from flask import Flask, request
import json

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print("=" * 50)
    print("🚨 GRAFANA ALERT RECEIVED!")
    print("=" * 50)
    
    if data and 'alerts' in data:
        for alert in data['alerts']:
            status = alert.get('status', 'unknown')
            name = alert.get('labels', {}).get('alertname', 'Unknown Alert')
            summary = alert.get('annotations', {}).get('summary', 'No summary')
            
            if status == 'firing':
                print(f"🔥 FIRING: {name}")
            else:
                print(f"✅ RESOLVED: {name}")
            
            print(f"📋 Summary: {summary}")
            print(f"🏷️  Labels: {alert.get('labels', {})}")
            print("-" * 30)
    
    return {"status": "ok"}

if __name__ == '__main__':
    print("🚀 Test Webhook Server starting on http://localhost:5001/webhook")
    app.run(host='0.0.0.0', port=5001, debug=True)