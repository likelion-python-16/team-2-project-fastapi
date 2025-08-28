/* ===========================
   Home page script
   - 검색 / 필터 / 추천 / 최신 / 팔로우
   - 카드 렌더링 & 페이지네이션
   - 프로필 드롭다운 & 인증 처리
   =========================== */

/* ---- 유틸: JWT 파싱 / 인증 헤더 / fetch 래퍼 ---- */
function parseJwt(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g,'+').replace(/_/g,'/');
    const json = decodeURIComponent(
      atob(base64).split('').map(c => '%' + ('00'+c.charCodeAt(0).toString(16)).slice(-2)).join('')
    );
    return JSON.parse(json);
  } catch (_) {
    return null;
  }
}
function getAccessToken() {
  return localStorage.getItem('access_token') || null;
}
function authHeader() {
  const t = getAccessToken();
  return t ? { 'Authorization': 'Bearer ' + t } : {};
}
async function fetchJSON(url, opts = {}) {
  const res = await fetch(url, {
    credentials: 'include',
    headers: { 'Accept': 'application/json', ...authHeader(), ...(opts.headers || {}) },
    ...opts
  });
  const ct = res.headers.get('content-type') || '';
  const isJSON = ct.includes('application/json');
  const body = isJSON ? await res.json() : await res.text();
  if (!res.ok) {
    const msg = (isJSON ? (body?.detail || body?.message) : body) || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return isJSON ? body : body;
}

/* ---- 전역 상태 ---- */
const S = {
  me: null,
  // 검색
  search: {
    query: '',
    filters: {
      status: 'recruiting',
      location: null,
      start_from: null,
      start_to: null,
      end_from: null,
      end_to: null,
      sort_by: 'created_at',
      sort_dir: 'desc'
    },
    page: 1,
    size: 12,
    total: 0,
    list: [],
    recommendations: []
  },
  // 홈 섹션
  home: {
    recommended: [],
    following: [],
    latest: [],
    latest_page: 1,
    latest_size: 12,
    latest_total: 0
  }
};

/* ---- DOM refs ---- */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const elLogo = $('#home-logo');
const elFiltersToggle = $('#filters-toggle');
const elFiltersPanel = $('#filters-panel');

const elSearchForm = $('#search-form');
const elSearchInput = $('#search-input');
const elSearchReset = $('#search-reset');

const elSearchArea = $('#search-area');
const elSearchEmpty = $('#search-empty');
const elSearchGrid = $('#search-grid');
const elSearchPag = $('#search-pagination');
const elRecEmpty = $('#rec-empty');
const elRecGrid = $('#rec-grid');

const elHomeSections = $('#home-sections');
const elHomeRecLoginReq = $('#rec-login-required');
const elHomeRecNotice = $('#rec-notice');
const elHomeRecList = $('#rec-list');
const elHomeFollowLoginReq = $('#follow-login-required');
const elHomeFollowList = $('#follow-list');
const elHomeLatestList = $('#latest-list');
const elHomeLatestPag = $('#latest-pagination');

// 필터들
const elFStatus = $('#f-status');
const elFLocation = $('#f-location');
const elFSf = $('#f-sf');
const elFSt = $('#f-st');
const elFEf = $('#f-ef');
const elFEt = $('#f-et');
const elFSortBy = $('#f-sortby');
const elFSortDir = $('#f-sortdir');

/* ---- 초기 세팅 ---- */
document.addEventListener('DOMContentLoaded', async () => {
  // 로고 → 홈
  elLogo?.addEventListener('click', (e) => {
    e.preventDefault();
    elSearchArea.style.display = 'none';
    elHomeSections.style.display = 'block';
    elSearchInput.value = '';
  });

  // 필터 토글
  elFiltersToggle?.addEventListener('click', () => {
    const open = elFiltersPanel.classList.toggle('open');
    elFiltersToggle.classList.toggle('open', open);
    elFiltersToggle.setAttribute('aria-expanded', String(open));
  });

  // 검색 제출
  elSearchForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    S.search.query = (elSearchInput.value || '').trim();
    S.search.page = 1;
    readFiltersIntoState();
    await doSearchFlow();
    
  });

  // 검색 초기화
  elSearchReset?.addEventListener('click', async () => {
    elSearchInput.value = '';
    clearFilters();
    S.search.query = '';
    S.search.page = 1;
    await doSearchFlow();
  });

  // 새로고침 버튼
  const elRefreshBtn = $('#refresh-btn');
  elRefreshBtn?.addEventListener('click', async () => {
    console.log('Manual refresh triggered');
    await performRefresh(elRefreshBtn);
  });

  // 프로필 드롭다운
  wireProfileDropdown();

  // 홈 섹션 로딩
  await bootstrapHome();

  // 페이지 포커스 시 데이터 리로드 (상태 변경 반영)
  let lastFocus = Date.now();
  window.addEventListener('focus', async () => {
    // 30초 이상 지났을 때만 리로드 (과도한 API 호출 방지)
    if (Date.now() - lastFocus > 30000) {
      console.log('Page focused, reloading data...');
      await bootstrapHome();
      lastFocus = Date.now();
    }
  });

  // 페이지를 떠날 때 시간 기록
  window.addEventListener('blur', () => {
    lastFocus = Date.now();
  });

  // localStorage 변경 감지 (다른 탭에서 챌린지 상태 변경 시)
  window.addEventListener('storage', async (e) => {
    if (e.key === 'challenge_status_changed' && e.newValue) {
      try {
        const changeEvent = JSON.parse(e.newValue);
        const timeDiff = Date.now() - changeEvent.timestamp;
        
        // 5분 이내의 변경사항만 처리 (오래된 이벤트 무시)
        if (timeDiff < 5 * 60 * 1000) {
          console.log('Challenge status changed in another tab, reloading...', changeEvent);
          await bootstrapHome();
          
          // 알림 표시 (선택적)
          showNotification(`챌린지 상태가 업데이트되었습니다.`);
        }
      } catch (error) {
        console.warn('Error processing status change event:', error);
      }
    }
  });

  // 페이지 로드 시에도 localStorage 확인
  checkForRecentStatusChanges();
});

/* ---- 프로필 드롭다운 ---- */
function wireProfileDropdown() {
  const dd = $('#profile-dd');
  const trigger = $('#profile-trigger');
  const menu = $('#profile-menu');

  const token = getAccessToken();
  let name = 'ME';
  if (token) {
    const p = parseJwt(token);
    if (p?.username) name = String(p.username).slice(0, 2).toUpperCase();
  }
  trigger.textContent = name;

  trigger.addEventListener('click', async () => {
    dd.classList.toggle('open');
    if (!dd.classList.contains('open')) return;

    // me 정보 로드 (선택)
    try {
      S.me = await fetchJSON('/api/v1/users/me');
    } catch (_) {
      S.me = null;
    }

    const isLogin = !!token && !!parseJwt(token);
    menu.innerHTML = `
      <div class="dropdown-item"><strong>${S.me?.username || 'Guest'}</strong></div>
      <div class="divider"></div>
      ${
        isLogin
          ? `
            <a class="dropdown-item" href="/dashboard">대시보드</a>
            <a class="dropdown-item" href="/pages/challenges/new">챌린지 생성</a>
            <div class="divider"></div>
            <button class="dropdown-item" id="logout-btn">로그아웃</button>
          `
          : `
            <a class="dropdown-item" href="/login">로그인</a>
            <a class="dropdown-item" href="/signup">회원가입</a>
          `
      }
    `;
    const logout = $('#logout-btn');
    logout?.addEventListener('click', () => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      location.href = '/login';
    });
  });

  // 외부 클릭 닫기
  document.addEventListener('click', (e) => {
    if (!dd.contains(e.target)) dd.classList.remove('open');
  });
}

/* ---- 홈 부트스트랩 ---- */
async function bootstrapHome() {
  // 추천
  await loadRecommended();

  // 팔로우 기반
  await loadFollowing();

  // 최신
  await loadLatest();

  // 기본은 홈 섹션 노출
  elHomeSections.style.display = 'block';
  elSearchArea.style.display = 'none';
}

/* ---- 추천 ---- */
async function loadRecommended() {
  const token = getAccessToken();
  if (!token) {
    elHomeRecLoginReq.style.display = 'block';
    elHomeRecNotice.style.display = 'none';
    elHomeRecList.innerHTML = '';
    return;
  }

  try {
    // 1순위: /api/v1/home/recommended
    let list = [];
    try {
      list = await fetchJSON('/api/v1/home/recommended');
    } catch (_) {
      // 2순위: /api/v1/challenges/recommended
      list = await fetchJSON('/api/v1/challenges/recommended');
    }

    if (!Array.isArray(list) || list.length === 0) {
      elHomeRecLoginReq.style.display = 'none';
      elHomeRecNotice.style.display = 'block';
      elHomeRecNotice.textContent = '아직 추천할 항목이 없어요. 관심사 태그를 추가해 보세요.';
      elHomeRecList.innerHTML = '';
      return;
    }

    elHomeRecLoginReq.style.display = 'none';
    elHomeRecNotice.style.display = 'none';
    elHomeRecList.innerHTML = renderCardList(list.slice(0, 6));
  } catch (e) {
    elHomeRecLoginReq.style.display = 'none';
    elHomeRecNotice.style.display = 'block';
    elHomeRecNotice.textContent = '추천 데이터를 불러오지 못했습니다.';
    elHomeRecList.innerHTML = '';
    console.warn(e);
  }
}

/* ---- 팔로우 기반 ---- */
async function loadFollowing() {
  const token = getAccessToken();
  if (!token) {
    elHomeFollowLoginReq.style.display = 'block';
    elHomeFollowList.innerHTML = '';
    return;
  }
  try {
    // 우리가 구현한 팔로우 API 사용
    const token = localStorage.getItem('access_token');
    const list = await fetchJSON('/api/v1/following/challenges', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    
    elHomeFollowLoginReq.style.display = 'none';
    elHomeFollowList.innerHTML = list?.length ? renderCardList(list.slice(0, 6)) : '<div class="empty">팔로우한 사용자의 챌린지가 없어요.</div>';
  } catch (e) {
    elHomeFollowLoginReq.style.display = 'none';
    elHomeFollowList.innerHTML = '<div class="empty">팔로우 데이터를 불러오지 못했습니다.</div>';
    console.warn('팔로우 챌린지 로드 실패:', e);
  }
}

/* ---- 최신 ---- */
async function loadLatest(page = 1) {
  S.home.latest_page = page;
  try {
    // 사용자 참여 상태가 포함된 챌린지 목록 사용
    const token = getAccessToken();
    let list = [];
    let total = 0;
    
    if (token) {
      // 로그인된 사용자: 참여 상태 포함 API 사용
      const data = await fetchJSON('/api/v1/challenges/with-participation');
      list = Array.isArray(data) ? data : [];
      
      // 페이지네이션을 위한 처리 (간단히 클라이언트 사이드에서 처리)
      const start = (S.home.latest_page - 1) * S.home.latest_size;
      const end = start + S.home.latest_size;
      const paginatedList = list.slice(start, end);
      total = list.length;
      list = paginatedList;
    } else {
      // 비로그인 사용자: 기존 API 사용
      const params = new URLSearchParams({
        sort: 'created_at',
        order: 'desc',
        page: String(S.home.latest_page),
        size: String(S.home.latest_size)
      });
      const data = await fetchJSON(`/api/v1/challenges?${params.toString()}`);
      list = Array.isArray(data?.items) ? data.items : (Array.isArray(data) ? data : data?.results || []);
      total = Number(data?.total || data?.count || (Array.isArray(data) ? data.length : 0));
    }

    S.home.latest = list;
    S.home.latest_total = total;

    elHomeLatestList.innerHTML = list?.length ? renderCardList(list) : '<div class="empty">등록된 챌린지가 없습니다.</div>';
    renderPagination(elHomeLatestPag, S.home.latest_page, Math.max(1, Math.ceil(total / S.home.latest_size)), (p)=>loadLatest(p));
  } catch (e) {
    elHomeLatestList.innerHTML = '<div class="empty">최신 챌린지를 불러오지 못했습니다.</div>';
    elHomeLatestPag.innerHTML = '';
    console.warn(e);
  }
}

/* ---- 검색 플로우 ---- */
function readFiltersIntoState() {
  S.search.filters.status = elFStatus.value || 'recruiting';
  S.search.filters.location = elFLocation.value || null;
  S.search.filters.start_from = elFSf.value || null;
  S.search.filters.start_to   = elFSt.value || null;
  S.search.filters.end_from   = elFEf.value || null;
  S.search.filters.end_to     = elFEt.value || null;
  S.search.filters.sort_by    = elFSortBy.value || 'created_at';
  S.search.filters.sort_dir   = elFSortDir.value || 'desc';
}
function clearFilters() {
  elFStatus.value = 'recruiting';
  elFLocation.value = '';
  elFSf.value = ''; elFSt.value = '';
  elFEf.value = ''; elFEt.value = '';
  elFSortBy.value = 'created_at';
  elFSortDir.value = 'desc';
  readFiltersIntoState();
}

async function doSearchFlow() {
  elHomeSections.style.display = 'none';
  elSearchArea.style.display = 'block';

  try {
    const qs = new URLSearchParams();
    if (S.search.query) qs.set('q', S.search.query);

    // 필터
    if (S.search.filters.status) qs.set('status', S.search.filters.status);
    if (S.search.filters.location) qs.set('location', S.search.filters.location);
    if (S.search.filters.start_from) qs.set('start_from', S.search.filters.start_from);
    if (S.search.filters.start_to)   qs.set('start_to', S.search.filters.start_to);
    if (S.search.filters.end_from)   qs.set('end_from', S.search.filters.end_from);
    if (S.search.filters.end_to)     qs.set('end_to', S.search.filters.end_to);
    if (S.search.filters.sort_by)    qs.set('sort', S.search.filters.sort_by);
    if (S.search.filters.sort_dir)   qs.set('order', S.search.filters.sort_dir);

    qs.set('page', String(S.search.page));
    qs.set('size', String(S.search.size));

    // /api/v1/challenges/search 사용
    const data = await fetchJSON(`/api/v1/challenges/search?${qs.toString()}`);
    
    // dual_search 응답 구조에 맞게 처리
    const list = data.matched_challenges || [];
    const recommendations = data.recommended_by_tag_challenges || [];
    
    S.search.list = list;
    S.search.total = list.length; // dual_search에서는 총 개수를 별도로 제공하지 않음
    S.search.recommendations = recommendations;

    // 렌더
    elSearchEmpty.style.display = list.length ? 'none' : 'block';
    elSearchEmpty.textContent = '검색 결과가 없습니다. 필터를 조정해 보세요.';
    elSearchGrid.innerHTML = list.length ? renderCardList(list) : '';

    if (recommendations?.length) {
      elRecEmpty.style.display = 'none';
      elRecGrid.innerHTML = renderCardList(recommendations.slice(0, 8));
    } else {
      elRecGrid.innerHTML = '';
      elRecEmpty.style.display = 'block';
    }

    renderPagination(elSearchPag, S.search.page, Math.max(1, Math.ceil(S.search.total / S.search.size)), async (p) => {
      S.search.page = p;
      await doSearchFlow();
    });

  } catch (e) {
    elSearchEmpty.style.display = 'block';
    elSearchEmpty.textContent = '검색 중 오류가 발생했습니다.';
    elSearchGrid.innerHTML = '';
    elSearchPag.innerHTML = '';
    console.warn(e);
  }
}

/* ---- 렌더러 ---- */
function renderCardList(list) {
  return list.map(ch => renderCard(ch)).join('');
}
function renderCard(ch) {
  // 필드 호환성
  const id = ch.id ?? ch.challenge_id;
  const title = ch.title || '(제목 없음)';
  const mode = (ch.mode || '').toLowerCase();
  const status = (ch.status || 'recruiting').toLowerCase();
  const start = ch.start_date || ch.starts_at || '';
  const end   = ch.end_date || ch.ends_at || '';
  const cover = ch.cover_image || ch.thumbnail || '';
  const paymentType = (ch.payment_type || 'free').toLowerCase();
  const entryFee = ch.entry_fee || 0;
  const monthlyFee = ch.monthly_fee || 0;
  
  // 참가 현황 정보
  const currentParticipants = ch.current_participants || 0;
  const maxParticipants = ch.max_participants;
  
  // 사용자 참여 상태
  const userParticipation = ch.user_participation;

  const paymentBadge = (() => {
    if (paymentType === 'free') return `<span class="badge free">무료</span>`;
    if (paymentType === 'entry_fee') return `<span class="badge paid">입장비 ${Number(entryFee).toLocaleString()}원</span>`;
    if (paymentType === 'monthly_fee') return `<span class="badge paid">월 ${Number(monthlyFee).toLocaleString()}원</span>`;
    if (paymentType === 'both') return `<span class="badge paid">입장비+월회비</span>`;
    return '';
  })();

  const statusBadge = (() => {
    if (status === 'recruiting') return `<span class="badge ok">모집중</span>`;
    if (status === 'active')     return `<span class="badge warn">진행중</span>`;
    if (status === 'completed')  return `<span class="badge">완료</span>`;
    if (status === 'cancelled')  return `<span class="badge">취소</span>`;
    return '';
  })();

  // 참가 현황 뱃지 (정원이 있을 때만 표시)
  const participantsBadge = (() => {
    if (maxParticipants && maxParticipants > 0) {
      const isFull = currentParticipants >= maxParticipants;
      const isNearFull = currentParticipants >= maxParticipants * 0.8;
      const badgeClass = isFull ? 'badge warn' : (isNearFull ? 'badge' : 'badge ok');
      return `<span class="${badgeClass}">👥 ${currentParticipants}/${maxParticipants}</span>`;
    } else if (currentParticipants > 0) {
      return `<span class="badge">👥 ${currentParticipants}명</span>`;
    }
    return '';
  })();

  // 사용자 참여 상태 뱃지
  const participationBadge = (() => {
    if (!userParticipation) return '';
    
    const participationStatus = userParticipation.status;
    const isCreator = userParticipation.is_creator;
    
    if (isCreator) {
      return `<span class="badge" style="background:#6366f1;color:white;border-color:#6366f1">👑 생성자</span>`;
    } else if (participationStatus === 'active') {
      return `<span class="badge" style="background:#10b981;color:white;border-color:#10b981">✅ 참가중</span>`;
    } else if (participationStatus === 'pending') {
      return `<span class="badge" style="background:#f59e0b;color:white;border-color:#f59e0b">⏳ 승인대기</span>`;
    } else if (participationStatus === 'payment_pending') {
      return `<span class="badge" style="background:#8b5cf6;color:white;border-color:#8b5cf6">💳 결제대기</span>`;
    }
    return '';
  })();

  const modeBadge = mode ? `<span class="badge">${mode}</span>` : '';

  const image = cover
    ? `<img class="thumb" src="${escapeHtml(cover)}" alt="thumb">`
    : `<div class="thumb"></div>`;

  return `
    <a class="card" href="/pages/challenges/${id}" title="${escapeHtml(title)}">
      ${image}
      <div class="card-body">
        <div class="title">${escapeHtml(title)}</div>
        <div class="meta">
          ${modeBadge}
          ${statusBadge}
          ${participationBadge}
          ${participantsBadge}
          ${paymentBadge}
          ${start ? `<span class="chip">시작 ${escapeHtml(start)}</span>` : ''}
          ${end ? `<span class="chip">종료 ${escapeHtml(end)}</span>` : ''}
        </div>
      </div>
    </a>
  `;
}
function escapeHtml(s='') {
  return String(s)
    .replaceAll('&','&amp;').replaceAll('<','&lt;')
    .replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
}


/* ---- 상태 변경 감지 관련 함수 ---- */
function checkForRecentStatusChanges() {
  try {
    const statusChangeStr = localStorage.getItem('challenge_status_changed');
    if (!statusChangeStr) return;
    
    const changeEvent = JSON.parse(statusChangeStr);
    const timeDiff = Date.now() - changeEvent.timestamp;
    
    // 30초 이내의 변경사항이면 자동 리로드
    if (timeDiff < 30 * 1000) {
      console.log('Recent challenge status change detected, reloading...', changeEvent);
      setTimeout(async () => {
        await bootstrapHome();
        showNotification('챌린지 목록이 업데이트되었습니다.');
      }, 1000); // 1초 후 리로드
    }
    
    // 처리된 이벤트 제거
    if (timeDiff > 5 * 60 * 1000) { // 5분 이상 된 것은 제거
      localStorage.removeItem('challenge_status_changed');
    }
  } catch (error) {
    console.warn('Error checking recent status changes:', error);
  }
}

async function performRefresh(btn) {
  if (!btn) return;
  
  const originalText = btn.textContent;
  btn.textContent = '🔄';
  btn.style.animation = 'spin 1s linear infinite';
  btn.disabled = true;
  
  try {
    await bootstrapHome();
    showNotification('챌린지 목록이 새로고침되었습니다.');
  } catch (error) {
    console.error('Refresh failed:', error);
    showNotification('새로고침 중 오류가 발생했습니다.');
  } finally {
    btn.textContent = originalText;
    btn.style.animation = '';
    btn.disabled = false;
  }
}

function showNotification(message) {
  // 간단한 알림 표시
  const notification = document.createElement('div');
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: #4338CA;
    color: white;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 14px;
    z-index: 1000;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    animation: slideIn 0.3s ease;
  `;
  notification.textContent = message;
  document.body.appendChild(notification);
  
  // 3초 후 제거
  setTimeout(() => {
    if (notification.parentNode) {
      notification.style.animation = 'slideOut 0.3s ease';
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
      }, 300);
    }
  }, 3000);
}

/* ---- 페이지네이션 ---- */
function renderPagination(container, page, pages, onClick) {
  if (!container) return;
  if (!pages || pages <= 1) {
    container.innerHTML = '';
    return;
  }
  const btn = (p, label, active=false) =>
    `<button class="page-btn ${active?'active':''}" data-page="${p}">${label}</button>`;

  let html = '';
  const start = Math.max(1, page - 2);
  const end = Math.min(pages, start + 4);
  if (page > 1) html += btn(page-1, 'Prev');
  for (let p = start; p <= end; p++) html += btn(p, p, p === page);
  if (page < pages) html += btn(page+1, 'Next');

  container.innerHTML = html;
  container.querySelectorAll('.page-btn').forEach(b => {
    b.addEventListener('click', () => {
      const p = parseInt(b.getAttribute('data-page'), 10);
      if (!isNaN(p)) onClick(p);
    });
  });
}
