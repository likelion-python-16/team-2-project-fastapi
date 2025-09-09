/**
 * 토스페이먼츠 v1 SDK 결제 연동 JavaScript
 * challenge_detail.html에서 사용
 */

// Import API utility from api.js (인증 토큰 포함)
import { api } from './api.js';

// Legacy fetchJSON for local use (인증이 필요하지 않은 경우)
async function fetchJSON(url, options = {}) {
    // 인증이 필요한 API는 api() 함수를 사용하세요
    const res = await fetch(url, {
        credentials: 'include',
        headers: { 'Accept': 'application/json', ...(options.headers || {}) },
        ...options
    });
    
    const contentType = res.headers.get('content-type') || '';
    const isJSON = contentType.includes('application/json');
    const body = isJSON ? await res.json() : await res.text();
    
    if (!res.ok) {
        const errorMessage = isJSON ? 
            (body?.detail || body?.message || `HTTP ${res.status}`) : 
            String(body);
        throw new Error(errorMessage);
    }
    
    return body;
}

// 메시지 표시 유틸리티
function setMessage(element, text, type = 'info') {
    if (!element) return;
    
    const colors = {
        'error': '#dc3545',
        'success': '#28a745', 
        'info': '#666',
        'warning': '#ffc107'
    };
    
    const color = colors[type] || colors.info;
    element.innerHTML = `<span style="color:${color}">${text}</span>`;
}

// 결제 UI 연결 함수
export function wirePaymentUI({ challengeId, getChallenge }) {
    const payButton = document.getElementById('btnPay');
    const messageElement = document.getElementById('joinPayMsg');
    
    if (!payButton || !challengeId) {
        console.warn('결제 UI 요소를 찾을 수 없습니다.');
        return;
    }
    
    // challengeId를 sessionStorage에 저장 (success 페이지에서 사용)
    sessionStorage.setItem('pay_challenge_id', challengeId);
    
    // 결제 버튼 클릭 이벤트
    payButton.addEventListener('click', async () => {
        setMessage(messageElement, '결제를 준비 중입니다...', 'info');
        payButton.disabled = true;
        
        try {
            // 1. 참여 신청 시도 (멱등성 보장 - 서버에서 처리)
            setMessage(messageElement, '참여 신청을 처리 중...', 'info');
            const participationResult = await api('/participations/join', {
                method: 'POST',
                body: { challenge_id: challengeId }
            });
            
            console.log('참여 신청 완료:', participationResult);
            
            // 참가 현황 새로고침 (전역 함수가 있다면)
            if (typeof refreshParticipationStatus === 'function') {
                try {
                    await refreshParticipationStatus();
                } catch (e) {
                    console.warn('참가 현황 업데이트 실패:', e);
                }
            }
            
            // 2. 결제 준비
            setMessage(messageElement, '결제 정보를 가져오는 중...', 'info');
            const paymentReady = await api('/payments/ready', { 
                method: 'POST',
                body: { challenge_id: challengeId }
            });
            
            const { orderId, amount, orderName, customerName, customerEmail, clientKey } = paymentReady;
            
            // 3. 토스페이먼츠 SDK 결제 요청
            if (!window.TossPayments) {
                throw new Error('토스페이먼츠 SDK가 로드되지 않았습니다. 페이지를 새로고침해주세요.');
            }
            
            setMessage(messageElement, '결제창을 여는 중...', 'info');
            const tossPayments = window.TossPayments(clientKey);
            
            // 결제 요청 (리다이렉트 방식)
            await tossPayments.requestPayment('카드', {
                amount: amount,
                orderId: orderId,
                orderName: orderName,
                customerName: customerName,
                customerEmail: customerEmail,
                successUrl: `${window.location.origin}/payments/success`,
                failUrl: `${window.location.origin}/payments/fail`
            });
            
        } catch (error) {
            console.error('결제 시작 실패:', error);
            setMessage(messageElement, `결제 시작 실패: ${error.message}`, 'error');
        } finally {
            payButton.disabled = false;
        }
    });
    
    // 초기화 시 챌린지 정보 확인
    if (typeof getChallenge === 'function') {
        getChallenge().then(challenge => {
            if (challenge && challenge.payment_type === 'free') {
                // 무료 챌린지인 경우 버튼 텍스트 변경
                payButton.textContent = '무료 참가';
                setMessage(messageElement, '이 챌린지는 무료입니다.', 'success');
            }
        }).catch(e => {
            console.error('챌린지 정보 로드 실패:', e);
        });
    }
}

// 결제 상태 확인 (선택사항)
export async function checkPaymentStatus(orderId) {
    try {
        const response = await fetchJSON(`/api/v1/payments/status?orderId=${orderId}`);
        return response;
    } catch (error) {
        console.error('결제 상태 확인 실패:', error);
        return null;
    }
}

// 결제 내역 조회
export async function getPaymentHistory() {
    try {
        const response = await fetchJSON('/api/v1/payments/history');
        return response.payments || [];
    } catch (error) {
        console.error('결제 내역 조회 실패:', error);
        return [];
    }
}