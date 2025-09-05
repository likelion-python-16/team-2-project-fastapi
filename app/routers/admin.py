from __future__ import annotations

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc

from app.core.database import get_db
from app.security import get_current_user
from app.models.user import User
from app.models.report import Report, ReportStatus, ReportAutoEval
from app.models.challenge import Challenge
from app.models.notification import Notification, NotificationEvent

router = APIRouter(tags=["Admin"])

def require_admin(current_user: User = Depends(get_current_user)):
    """관리자 권한 확인"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다"
        )
    return current_user

@router.get("/admin/reports", response_class=HTMLResponse)
def admin_reports_page(
    token: str = Query(None, description="Access token for authentication"),
    db: Session = Depends(get_db)
):
    """관리자 신고 관리 페이지"""
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>신고 관리 - 관리자</title>
        <style>
            :root {
                --primary: #4338CA;
                --danger: #DC2626;
                --success: #059669;
                --warning: #D97706;
                --gray: #6B7280;
                --light-gray: #F3F4F6;
                --border: #E5E7EB;
            }
            
            * { box-sizing: border-box; }
            body { 
                font-family: Inter, system-ui, sans-serif; 
                margin: 0; 
                background: #F9FAFB; 
                color: #111827;
            }
            
            .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
            
            .header {
                background: white;
                padding: 20px;
                border-radius: 12px;
                margin-bottom: 20px;
                border: 1px solid var(--border);
            }
            
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 16px;
                margin-bottom: 20px;
            }
            
            .stat-card {
                background: white;
                padding: 20px;
                border-radius: 12px;
                border: 1px solid var(--border);
                text-align: center;
            }
            
            .stat-number {
                font-size: 2rem;
                font-weight: 800;
                color: var(--primary);
                display: block;
            }
            
            .stat-label {
                color: var(--gray);
                margin-top: 8px;
                font-size: 14px;
            }
            
            .filters {
                background: white;
                padding: 20px;
                border-radius: 12px;
                margin-bottom: 20px;
                border: 1px solid var(--border);
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
                align-items: center;
            }
            
            .filter-group {
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .filter-group label {
                font-weight: 600;
                color: var(--gray);
            }
            
            select, input {
                padding: 8px 12px;
                border: 1px solid var(--border);
                border-radius: 6px;
                font-size: 14px;
            }
            
            .btn {
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
                font-weight: 600;
                cursor: pointer;
                text-decoration: none;
                display: inline-flex;
                align-items: center;
                gap: 4px;
            }
            
            .btn-primary { background: var(--primary); color: white; }
            .btn-success { background: var(--success); color: white; }
            .btn-danger { background: var(--danger); color: white; }
            .btn-secondary { background: var(--light-gray); color: var(--gray); }
            
            .reports-table {
                background: white;
                border-radius: 12px;
                overflow: hidden;
                border: 1px solid var(--border);
            }
            
            table {
                width: 100%;
                border-collapse: collapse;
            }
            
            th {
                background: var(--light-gray);
                padding: 12px;
                text-align: left;
                font-weight: 600;
                color: var(--gray);
                border-bottom: 1px solid var(--border);
            }
            
            td {
                padding: 12px;
                border-bottom: 1px solid var(--border);
            }
            
            .status-badge {
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
            }
            
            .status-pending { background: #FEF3C7; color: #92400E; }
            .status-reviewed { background: #D1FAE5; color: #065F46; }
            .status-rejected { background: #FEE2E2; color: #991B1B; }
            
            .auto-decision {
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 600;
            }
            
            .auto-true { background: #FEE2E2; color: #991B1B; }
            .auto-false { background: #D1FAE5; color: #065F46; }
            .auto-review { background: #FEF3C7; color: #92400E; }
            
            .pagination {
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 8px;
                margin-top: 20px;
            }
            
            .modal {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                z-index: 1000;
            }
            
            .modal-content {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: white;
                padding: 24px;
                border-radius: 12px;
                width: 90%;
                max-width: 500px;
                max-height: 80vh;
                overflow-y: auto;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>신고 관리 시스템</h1>
                <p>사용자 신고를 검토하고 처리할 수 있습니다.</p>
            </div>
            
            <div class="stats" id="statsContainer">
                <!-- 통계 데이터가 여기에 로드됩니다 -->
            </div>
            
            <div class="filters">
                <div class="filter-group">
                    <label>상태:</label>
                    <select id="statusFilter">
                        <option value="">전체</option>
                        <option value="pending">대기중</option>
                        <option value="reviewed">처리완료</option>
                        <option value="rejected">반려</option>
                    </select>
                </div>
                
                <div class="filter-group">
                    <label>자동판정:</label>
                    <select id="autoDecisionFilter">
                        <option value="">전체</option>
                        <option value="true">위반</option>
                        <option value="false">정상</option>
                        <option value="review">검토필요</option>
                    </select>
                </div>
                
                <div class="filter-group">
                    <label>기간:</label>
                    <select id="dateFilter">
                        <option value="7">최근 7일</option>
                        <option value="30">최근 30일</option>
                        <option value="90">최근 90일</option>
                        <option value="">전체</option>
                    </select>
                </div>
                
                <button class="btn btn-primary" onclick="loadReports()">필터 적용</button>
                <button class="btn btn-secondary" onclick="resetFilters()">초기화</button>
            </div>
            
            <div class="reports-table">
                <table>
                    <thead>
                        <tr>
                            <th>신고 ID</th>
                            <th>신고자(ID)</th>
                            <th>신고대상</th>
                            <th>신고사유</th>
                            <th>자동판정</th>
                            <th>신뢰도</th>
                            <th>상태</th>
                            <th>신고일시</th>
                            <th>작업</th>
                        </tr>
                    </thead>
                    <tbody id="reportsTableBody">
                        <!-- 신고 데이터가 여기에 로드됩니다 -->
                    </tbody>
                </table>
            </div>
            
            <div class="pagination" id="pagination">
                <!-- 페이지네이션이 여기에 로드됩니다 -->
            </div>
        </div>
        
        <!-- 신고 상세 모달 -->
        <div id="reportModal" class="modal">
            <div class="modal-content">
                <div id="modalContent">
                    <!-- 모달 내용이 여기에 로드됩니다 -->
                </div>
            </div>
        </div>
        
        <script>
            let currentPage = 1;
            const pageSize = 20;
            
            // 페이지 로드시 데이터 로드
            document.addEventListener('DOMContentLoaded', function() {
                checkAuth();
            });
            
            // 인증 확인
            function checkAuth() {
                const token = getToken();
                if (!token) {
                    showLoginForm();
                } else {
                    // 토큰이 있으면 유효성 확인
                    fetch('/api/v1/auth/me', {
                        headers: { 'Authorization': 'Bearer ' + token }
                    }).then(r => {
                        if (r.ok) {
                            return r.json();
                        } else {
                            throw new Error('Invalid token');
                        }
                    }).then(user => {
                        if (!user.is_admin) {
                            alert('관리자 권한이 필요합니다.');
                            showLoginForm();
                        } else {
                            hideLoginForm();
                            loadStats();
                            loadReports();
                        }
                    }).catch(() => {
                        showLoginForm();
                    });
                }
            }
            
            // 로그인 폼 표시
            function showLoginForm() {
                const loginHtml = `
                    <div id="loginOverlay" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 10000; display: flex; align-items: center; justify-content: center;">
                        <div style="background: white; padding: 32px; border-radius: 12px; width: 90%; max-width: 400px;">
                            <h2 style="margin: 0 0 20px; text-align: center;">관리자 로그인</h2>
                            <form id="adminLoginForm" onsubmit="adminLogin(event)">
                                <div style="margin-bottom: 16px;">
                                    <label style="display: block; margin-bottom: 4px; font-weight: 600;">아이디:</label>
                                    <input type="text" id="adminUsername" required style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px;">
                                </div>
                                <div style="margin-bottom: 20px;">
                                    <label style="display: block; margin-bottom: 4px; font-weight: 600;">비밀번호:</label>
                                    <input type="password" id="adminPassword" required style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px;">
                                </div>
                                <button type="submit" style="width: 100%; padding: 12px; background: var(--primary); color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer;">로그인</button>
                            </form>
                        </div>
                    </div>
                `;
                document.body.insertAdjacentHTML('beforeend', loginHtml);
            }
            
            // 로그인 폼 숨기기
            function hideLoginForm() {
                const overlay = document.getElementById('loginOverlay');
                if (overlay) overlay.remove();
            }
            
            // 관리자 로그인 처리
            async function adminLogin(event) {
                event.preventDefault();
                const username = document.getElementById('adminUsername').value;
                const password = document.getElementById('adminPassword').value;
                
                try {
                    const response = await fetch('/api/v1/auth/login', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            login: username,
                            password: password
                        })
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        localStorage.setItem('access_token', data.access_token);
                        
                        // 관리자 권한 확인
                        const userResponse = await fetch('/api/v1/auth/me', {
                            headers: { 'Authorization': 'Bearer ' + data.access_token }
                        });
                        
                        if (userResponse.ok) {
                            const user = await userResponse.json();
                            if (user.is_admin) {
                                hideLoginForm();
                                loadStats();
                                loadReports();
                            } else {
                                alert('관리자 권한이 필요합니다.');
                            }
                        }
                    } else {
                        alert('로그인에 실패했습니다. 아이디와 비밀번호를 확인해주세요.');
                    }
                } catch (error) {
                    alert('로그인 중 오류가 발생했습니다.');
                }
            }
            
            // 통계 데이터 로드
            async function loadStats() {
                try {
                    const response = await fetch('/api/v1/admin/reports/stats', {
                        headers: {
                            'Authorization': 'Bearer ' + getToken()
                        }
                    });
                    
                    if (response.ok) {
                        const stats = await response.json();
                        renderStats(stats);
                    }
                } catch (error) {
                    console.error('통계 로드 오류:', error);
                }
            }
            
            // 신고 목록 로드
            async function loadReports() {
                const status = document.getElementById('statusFilter').value;
                const autoDecision = document.getElementById('autoDecisionFilter').value;
                const days = document.getElementById('dateFilter').value;
                
                let url = `/api/v1/admin/reports-data?page=${currentPage}&size=${pageSize}`;
                if (status) url += `&status=${status}`;
                if (autoDecision) url += `&auto_decision=${autoDecision}`;
                if (days) url += `&days=${days}`;
                
                try {
                    const response = await fetch(url, {
                        headers: {
                            'Authorization': 'Bearer ' + getToken(),
                            'Accept': 'application/json'
                        }
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        renderReports(data.items);
                        renderPagination(data.total, data.page, data.size);
                    } else {
                        console.error('신고 목록 로드 실패:', response.status, response.statusText);
                    }
                } catch (error) {
                    console.error('신고 목록 로드 오류:', error);
                }
            }
            
            // 통계 렌더링
            function renderStats(stats) {
                const container = document.getElementById('statsContainer');
                container.innerHTML = `
                    <div class="stat-card">
                        <span class="stat-number">${stats.total_reports || 0}</span>
                        <div class="stat-label">총 신고</div>
                    </div>
                    <div class="stat-card">
                        <span class="stat-number">${stats.pending_reports || 0}</span>
                        <div class="stat-label">대기중</div>
                    </div>
                    <div class="stat-card">
                        <span class="stat-number">${stats.auto_violations || 0}</span>
                        <div class="stat-label">자동 위반</div>
                    </div>
                    <div class="stat-card">
                        <span class="stat-number">${stats.need_review || 0}</span>
                        <div class="stat-label">검토 필요</div>
                    </div>
                `;
            }
            
            // 신고 목록 렌더링
            function renderReports(reports) {
                const tbody = document.getElementById('reportsTableBody');
                tbody.innerHTML = reports.map(report => `
                    <tr>
                        <td>${report.id}</td>
                        <td>${report.reporter_username || report.reporter_name || 'N/A'}</td>
                        <td>${report.reported_name || report.reported_username || 'N/A'}</td>
                        <td>${getReasonText(report.reason)}</td>
                        <td>
                            <span class="auto-decision auto-${report.auto_eval?.auto_decision || 'review'}">
                                ${getAutoDecisionText(report.auto_eval?.auto_decision)}
                            </span>
                        </td>
                        <td>${report.auto_eval?.auto_confidence || 0}%</td>
                        <td>
                            <span class="status-badge status-${report.status}">
                                ${getStatusText(report.status)}
                            </span>
                        </td>
                        <td>${formatDate(report.created_at)}</td>
                        <td>
                            <button class="btn btn-primary" onclick="viewReport(${report.id})">상세</button>
                        </td>
                    </tr>
                `).join('');
            }
            
            // 신고 상세 보기
            async function viewReport(reportId) {
                try {
                    const response = await fetch(`/api/v1/admin/reports-data/${reportId}`, {
                        headers: {
                            'Authorization': 'Bearer ' + getToken(),
                            'Accept': 'application/json'
                        }
                    });
                    
                    if (response.ok) {
                        const report = await response.json();
                        showReportModal(report);
                    } else {
                        console.error('신고 상세 로드 실패:', response.status);
                    }
                } catch (error) {
                    console.error('신고 상세 로드 오류:', error);
                }
            }
            
            // 신고 모달 표시
            function showReportModal(report) {
                const modal = document.getElementById('reportModal');
                const content = document.getElementById('modalContent');
                
                content.innerHTML = `
                    <h3>신고 상세 정보 #${report.id}</h3>
                    <div style="margin-bottom: 16px;">
                        <strong>신고자:</strong> ${report.reporter_username || report.reporter_name || 'N/A'}<br>
                        <strong>신고대상:</strong> ${report.reported_name || report.reported_username || 'N/A'}<br>
                        <strong>챌린지:</strong> ${report.challenge_title || 'N/A'}<br>
                        <strong>신고사유:</strong> ${getReasonText(report.reason)}<br>
                        <strong>신고일시:</strong> ${formatDate(report.created_at)}
                    </div>
                    
                    <div style="margin-bottom: 16px;">
                        <strong>신고 내용:</strong><br>
                        <div style="background: #f9fafb; padding: 12px; border-radius: 6px; margin-top: 8px;">
                            ${report.details || '내용 없음'}
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 20px;">
                        <h4>자동 평가 결과</h4>
                        <table style="width: 100%; font-size: 14px;">
                            <tr><td><strong>자동 판정:</strong></td><td>${getAutoDecisionText(report.auto_eval?.auto_decision)}</td></tr>
                            <tr><td><strong>신뢰도:</strong></td><td>${report.auto_eval?.auto_confidence || 0}%</td></tr>
                            <tr><td><strong>독성 점수:</strong></td><td>${report.auto_eval?.toxic_score || 0}%</td></tr>
                            <tr><td><strong>규칙 위반:</strong></td><td>${report.auto_eval?.rule_flag ? '예' : '아니오'}</td></tr>
                            <tr><td><strong>신고자 신뢰도:</strong></td><td>${report.auto_eval?.reporter_trust || 0}%</td></tr>
                        </table>
                    </div>
                    
                    ${report.status === 'pending' ? `
                    <div style="display: flex; gap: 8px; justify-content: flex-end;">
                        <button class="btn btn-success" onclick="processReport(${report.id}, 'approve')">승인</button>
                        <button class="btn btn-danger" onclick="processReport(${report.id}, 'reject')">반려</button>
                        <button class="btn btn-secondary" onclick="closeModal()">닫기</button>
                    </div>
                    ` : `
                    <div style="display: flex; gap: 8px; justify-content: flex-end;">
                        <button class="btn btn-secondary" onclick="closeModal()">닫기</button>
                    </div>
                    `}
                `;
                
                modal.style.display = 'block';
            }
            
            // 신고 처리
            async function processReport(reportId, action) {
                try {
                    const response = await fetch(`/api/v1/admin/reports-data/${reportId}/${action}`, {
                        method: 'POST',
                        headers: {
                            'Authorization': 'Bearer ' + getToken(),
                            'Content-Type': 'application/json'
                        }
                    });
                    
                    if (response.ok) {
                        const result = await response.json();
                        if (action === 'approve' && result.penalty_type) {
                            alert(`신고 승인 완료!\n\n제재 내용: ${result.penalty_type}\n경고 횟수: ${result.warning_count}회\n매너점수: ${result.manner_score}점`);
                        } else {
                            alert(result.message || `신고가 ${action === 'approve' ? '승인' : '반려'}되었습니다.`);
                        }
                        closeModal();
                        loadReports();
                        loadStats();
                    } else {
                        const errorData = await response.json().catch(() => ({}));
                        alert('처리 중 오류가 발생했습니다: ' + (errorData.detail || '알 수 없는 오류'));
                    }
                } catch (error) {
                    console.error('신고 처리 오류:', error);
                    alert('신고 처리 중 오류가 발생했습니다.');
                }
            }
            
            // 모달 닫기
            function closeModal() {
                document.getElementById('reportModal').style.display = 'none';
            }
            
            // 필터 초기화
            function resetFilters() {
                document.getElementById('statusFilter').value = '';
                document.getElementById('autoDecisionFilter').value = '';
                document.getElementById('dateFilter').value = '7';
                currentPage = 1;
                loadReports();
            }
            
            // 유틸리티 함수들
            function getToken() {
                return localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
            }
            
            function getReasonText(reason) {
                const reasons = {
                    'inappropriate_behavior': '부적절한 행동',
                    'spam': '스팸/광고',
                    'harassment': '괴롭힘',
                    'fake_profile': '가짜 프로필',
                    'other': '기타'
                };
                return reasons[reason] || reason;
            }
            
            function getStatusText(status) {
                const statuses = {
                    'pending': '대기중',
                    'reviewed': '처리완료',
                    'rejected': '반려'
                };
                return statuses[status] || status;
            }
            
            function getAutoDecisionText(decision) {
                const decisions = {
                    'true': '위반',
                    'false': '정상',
                    'review': '검토필요'
                };
                return decisions[decision] || '알 수 없음';
            }
            
            function formatDate(dateString) {
                if (!dateString) return 'N/A';
                return new Date(dateString).toLocaleString('ko-KR', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            }
            
            function renderPagination(total, page, size) {
                const totalPages = Math.ceil(total / size);
                const pagination = document.getElementById('pagination');
                
                let html = '';
                if (page > 1) {
                    html += `<button class="btn btn-secondary" onclick="goToPage(${page - 1})">이전</button>`;
                }
                
                html += `<span>페이지 ${page} / ${totalPages} (총 ${total}개)</span>`;
                
                if (page < totalPages) {
                    html += `<button class="btn btn-secondary" onclick="goToPage(${page + 1})">다음</button>`;
                }
                
                pagination.innerHTML = html;
            }
            
            function goToPage(page) {
                currentPage = page;
                loadReports();
            }
            
            // 모달 외부 클릭시 닫기
            document.getElementById('reportModal').addEventListener('click', function(e) {
                if (e.target === this) {
                    closeModal();
                }
            });
        </script>
    </body>
    </html>
    """

@router.get("/admin/reports/stats")
def get_report_stats(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """신고 통계 정보"""
    stats = {}
    
    # 총 신고 수
    stats['total_reports'] = db.query(func.count(Report.id)).scalar() or 0
    
    # 대기중인 신고
    stats['pending_reports'] = db.query(func.count(Report.id)).filter(
        Report.status == ReportStatus.pending
    ).scalar() or 0
    
    # 자동 위반 판정
    stats['auto_violations'] = db.query(func.count(ReportAutoEval.id)).filter(
        ReportAutoEval.auto_decision == 'true'
    ).scalar() or 0
    
    # 검토 필요
    stats['need_review'] = db.query(func.count(ReportAutoEval.id)).filter(
        ReportAutoEval.auto_decision == 'review'
    ).scalar() or 0
    
    return stats

@router.get("/admin/reports-data")
def get_admin_reports(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    auto_decision: str = Query(None),
    days: int = Query(None),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """관리자용 신고 목록"""
    query = db.query(Report).options(
        joinedload(Report.reporter),
        joinedload(Report.reported),
        joinedload(Report.challenge)
    )
    
    # 상태 필터
    if status:
        query = query.filter(Report.status == status)
    
    # 기간 필터
    if days:
        since = datetime.now() - timedelta(days=int(days))
        query = query.filter(Report.created_at >= since)
    
    # 자동 판정 필터
    if auto_decision:
        query = query.join(ReportAutoEval).filter(
            ReportAutoEval.auto_decision == auto_decision
        )
    
    # 총 개수
    total = query.count()
    
    # 페이지네이션 적용
    reports = query.order_by(desc(Report.created_at)).offset((page - 1) * size).limit(size).all()
    
    # 응답 데이터 구성
    items = []
    for report in reports:
        # 자동 평가 데이터 조회
        auto_eval = db.query(ReportAutoEval).filter(
            ReportAutoEval.report_id == report.id
        ).first()
        
        items.append({
            'id': report.id,
            'reporter_username': report.reporter.username if report.reporter else None,
            'reporter_name': report.reporter.name if report.reporter else None,
            'reported_username': report.reported.username if report.reported else None,
            'reported_name': report.reported.name if report.reported else None,
            'challenge_title': report.challenge.title if report.challenge else None,
            'reason': report.reason,
            'details': report.details,
            'status': report.status.value if hasattr(report.status, 'value') else str(report.status),
            'created_at': report.created_at,
            'auto_eval': {
                'auto_decision': auto_eval.auto_decision.value if auto_eval and hasattr(auto_eval.auto_decision, 'value') else str(auto_eval.auto_decision) if auto_eval else None,
                'auto_confidence': auto_eval.auto_confidence if auto_eval else 0,
                'toxic_score': auto_eval.toxic_score if auto_eval else 0,
                'rule_flag': auto_eval.rule_flag if auto_eval else False,
                'reporter_trust': auto_eval.reporter_trust if auto_eval else 0,
            } if auto_eval else None
        })
    
    return {
        'items': items,
        'total': total,
        'page': page,
        'size': size,
        'pages': (total + size - 1) // size
    }

@router.get("/admin/reports-data/{report_id}")
def get_admin_report(
    report_id: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """관리자용 신고 상세 정보"""
    report = db.query(Report).options(
        joinedload(Report.reporter),
        joinedload(Report.reported),
        joinedload(Report.challenge)
    ).filter(Report.id == report_id).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="신고를 찾을 수 없습니다")
    
    # 자동 평가 데이터
    auto_eval = db.query(ReportAutoEval).filter(
        ReportAutoEval.report_id == report.id
    ).first()
    
    return {
        'id': report.id,
        'reporter_username': report.reporter.username if report.reporter else None,
        'reporter_name': report.reporter.name if report.reporter else None,
        'reported_username': report.reported.username if report.reported else None,
        'reported_name': report.reported.name if report.reported else None,
        'challenge_title': report.challenge.title if report.challenge else None,
        'reason': report.reason,
        'details': report.details,
        'status': report.status.value if hasattr(report.status, 'value') else str(report.status),
        'created_at': report.created_at,
        'auto_eval': {
            'auto_decision': auto_eval.auto_decision.value if auto_eval and hasattr(auto_eval.auto_decision, 'value') else str(auto_eval.auto_decision) if auto_eval else None,
            'auto_confidence': auto_eval.auto_confidence if auto_eval else 0,
            'toxic_score': auto_eval.toxic_score if auto_eval else 0,
            'rule_flag': auto_eval.rule_flag if auto_eval else False,
            'reporter_trust': auto_eval.reporter_trust if auto_eval else 0,
        } if auto_eval else None
    }

@router.post("/admin/reports-data/{report_id}/approve")
def approve_report(
    report_id: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """신고 승인"""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="신고를 찾을 수 없습니다")
    
    # 신고 대상자에게 제재 적용
    reported_user = report.reported
    if reported_user:
        penalty_type = reported_user.apply_report_penalty()
        
        # 사용자 변경사항 먼저 저장
        db.add(reported_user)
        db.commit()
        db.refresh(reported_user)
        
        # 신고당한 사용자에게 알림 생성
        if penalty_type == "리뷰 작성 금지":
            notification = Notification(
                user_id=reported_user.id,
                title="⚠️ 신고 누적으로 인한 제재",
                content=f"신고가 승인되어 리뷰 작성이 금지되었습니다. 매너점수 -3점",
                event_type=NotificationEvent.warning_received,
                target_type="user",
                target_id=reported_user.id
            )
        else:
            notification = Notification(
                user_id=reported_user.id,
                title="⚠️ 신고 접수 알림",
                content=f"신고가 접수되어 1회 경고가 부여되었습니다. 매너점수 -3점",
                event_type=NotificationEvent.report_received,
                target_type="report",
                target_id=report.id
            )
        
        db.add(notification)
        
        # 신고 상태 변경
        report.status = ReportStatus.resolved
        report.is_false_report = False
        db.commit()
        
        return {
            "message": f"신고가 승인되었습니다. {reported_user.name}님에게 {penalty_type} 조치가 적용되었습니다.",
            "penalty_type": penalty_type,
            "warning_count": reported_user.warning_count,
            "manner_score": reported_user.manner_score
        }
    else:
        report.status = ReportStatus.resolved
        report.is_false_report = False
        db.commit()
        
        return {"message": "신고가 승인되었습니다 (대상자를 찾을 수 없음)"}

@router.post("/admin/reports-data/{report_id}/reject")
def reject_report(
    report_id: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """신고 반려"""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="신고를 찾을 수 없습니다")
    
    report.status = ReportStatus.rejected
    report.is_false_report = True
    db.commit()
    
    return {"message": "신고가 반려되었습니다"}