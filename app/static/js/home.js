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
  // Prefer persistent token; fall back to session token
  return (
    localStorage.getItem('access_token') ||
    sessionStorage.getItem('access_token') ||
    null
  );
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

/* ---- Admin 모드 전환 ---- */
async function enterAdminMode() {
  try {
    const response = await fetch('/admin/mode/enable', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getAccessToken()}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (response.ok) {
      // 관리자 모드 활성화 성공 - 페이지 이동
      window.location.href = '/admin';
    } else {
      const errorData = await response.json();
      alert(errorData.detail || '관리자 모드 전환에 실패했습니다.');
    }
  } catch (error) {
    console.error('Admin mode error:', error);
    alert('관리자 모드 전환 중 오류가 발생했습니다.');
  }
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

/* ---- Avatar helpers ---- */
const DEFAULT_AVATAR_URL = '/static/pictures/defaultprofile.jpeg';
function normalizeAvatarUrl(raw) {
  if (!raw || typeof raw !== 'string') return DEFAULT_AVATAR_URL;
  let url = raw.trim();
  // Ensure https for external images
  if (url.startsWith('//')) url = 'https:' + url;
  if (url.startsWith('http://lh3.googleusercontent.com')) url = url.replace('http://', 'https://');
  // Google avatar sizing: add size if missing
  if (/\.googleusercontent\.com\//.test(url) && !(/[?&]sz=\d+/.test(url) || /=(s|w)\d+/.test(url))) {
    url += (url.includes('?') ? '&' : '?') + 'sz=96';
  }
  return url;
}
function getAvatarUrl(user) {
  try {
    const raw = user?.profile_image_url || user?.profile_image || user?.avatar_url || user?.avatar;
    return normalizeAvatarUrl(raw);
  } catch (_) {
    return DEFAULT_AVATAR_URL;
  }
}

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
  // Resolve user (prefer API; fall back to token payload) and set avatar
  (async () => {
    try {
      if (token) {
        try {
          S.me = await fetchJSON('/api/v1/users/me');
        } catch (_) {
          const p = parseJwt(token) || {};
          if (p && (p.sub || p.user_id)) {
            S.me = { id: p.user_id || null, username: p.sub || null };
          } else {
            S.me = null;
          }
        }
      } else {
        try { S.me = await fetchJSON('/api/v1/users/me'); } catch (_) { S.me = null; }
      }
    } catch (_) { S.me = null; }
    const avatarUrl = getAvatarUrl(S.me || {});
    const img = new Image();
    img.alt = 'avatar';
    img.referrerPolicy = 'no-referrer';
    img.style.cssText = 'width:36px;height:36px;border-radius:50%;object-fit:cover;display:block;';
    img.src = avatarUrl;
    img.onerror = () => { img.src = DEFAULT_AVATAR_URL; };
    trigger.innerHTML = '';
    trigger.appendChild(img);

    // Toggle login button vs avatar dropdown on init
    const loginBtn = document.getElementById('login-btn');
    const isLoginInit = !!S.me || (!!token && !!parseJwt(token));
    if (isLoginInit) {
      if (loginBtn) loginBtn.style.display = 'none';
      dd.style.display = '';
    } else {
      if (loginBtn) loginBtn.style.display = 'inline-flex';
      dd.style.display = 'none';
    }
  })();

  async function populateMenu() {
    // me 정보 로드/갱신 (있으면 갱신 시도)
    try { S.me = await fetchJSON('/api/v1/users/me'); } catch (_) { /* keep S.me */ }

    const tk = getAccessToken();
    const isLogin = !!S.me || (!!tk && !!parseJwt(tk));
    const isAdmin = S.me?.is_admin || S.me?.is_superadmin || false;

    // Toggle login button vs avatar dropdown dynamically
    const loginBtn = document.getElementById('login-btn');
    if (isLogin) {
      if (loginBtn) loginBtn.style.display = 'none';
      dd.style.display = '';
    } else {
      if (loginBtn) loginBtn.style.display = 'inline-flex';
      dd.style.display = 'none';
      return; // no menu for guests
    }
    
    menu.innerHTML = `
      ${S.me?.username ? `<div class=\"dropdown-item\"><strong>${S.me.username}</strong></div><div class=\"divider\"></div>` : ''}
      ${isLogin ? `
        <a class="dropdown-item" href="/mypage">마이페이지</a>
        <a class="dropdown-item" href="/account/edit">회원정보 수정</a>
      ` : `
        <a class="dropdown-item" href="/login">로그인</a>
        <a class="dropdown-item" href="/signup">회원가입</a>
      `}
    `;
    if (isLogin) {
      const divider = document.createElement('div');
      divider.className = 'divider';
      const btn = document.createElement('button');
      btn.id = 'logout-btn';
      btn.type = 'button';
      btn.className = 'dropdown-item';
      btn.textContent = '로그아웃';
      menu.appendChild(divider);
      menu.appendChild(btn);
      btn.addEventListener('click', async () => {
        try { await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' }); } catch (_) {}
        try { localStorage.removeItem('access_token'); } catch (_) {}
        try { sessionStorage.removeItem('access_token'); } catch (_) {}
        window.location.href = '/home';
      });
    }
  }

  // Hover open/close
  function openMenu(){ dd.classList.add('open'); }
  function closeMenu(){ dd.classList.remove('open'); }
  let hoverTimer = null;
  trigger.addEventListener('mouseenter', async () => { clearTimeout(hoverTimer); openMenu(); await populateMenu(); });
  dd.addEventListener('mouseenter', () => { clearTimeout(hoverTimer); });
  dd.addEventListener('mouseleave', () => { hoverTimer = setTimeout(closeMenu, 100); });
  // Keyboard focus support
  trigger.addEventListener('focus', async () => { openMenu(); await populateMenu(); });
  dd.addEventListener('focusout', (e) => { if (!dd.contains(e.relatedTarget)) closeMenu(); });

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
  try {
    // Guests: hide the whole Recommended section
    const hasToken = !!getAccessToken();
    if (!hasToken) {
      const sec = elHomeRecList?.closest('.section');
      if (sec) sec.style.display = 'none';
      return;
    }
    // 1순위: /api/v1/home/recommended (객체 응답 {success, challenges})
    let res = await fetchJSON('/api/v1/home/recommended');
    let list = Array.isArray(res?.challenges) ? res.challenges : (Array.isArray(res) ? res : []);
    const personalized = !!res?.personalized;

    // 2순위: /api/v1/challenges/recommended (존재하지 않을 수 있음)
    if (!list.length) {
      try {
        const r2 = await fetchJSON('/api/v1/challenges/recommended');
        list = Array.isArray(r2) ? r2 : (Array.isArray(r2?.items) ? r2.items : []);
      } catch (_) {}
    }

    if (!list.length) {
      // 로그인 상태에서만 안내, 게스트는 섹션 숨김
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
    // 실패 시 조용히 숨김
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
    // Guests: hide the whole Following section
    const sec = elHomeFollowList?.closest('.section');
    if (sec) sec.style.display = 'none';
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
    let list = [];
    let total = 0;

    // 1차 시도: 정렬/페이지 파라미터 지원 버전
    try {
      const params = new URLSearchParams({
        sort: 'created_at', order: 'desc',
        page: String(S.home.latest_page), size: String(S.home.latest_size)
      });
      const data = await fetchJSON(`/api/v1/challenges?${params.toString()}`);
      list = Array.isArray(data?.items) ? data.items : (Array.isArray(data) ? data : data?.results || []);
      total = Number(data?.total || data?.count || (Array.isArray(data) ? data.length : 0));
    } catch (_) {
      // 2차 시도: 상태별 엔드포인트 (recruiting)
      try {
        const data = await fetchJSON('/api/v1/challenges/status/recruiting');
        list = Array.isArray(data) ? data : [];
        total = list.length;
      } catch (__) {
        // 3차 시도: 기본 목록
        const data = await fetchJSON('/api/v1/challenges');
        list = Array.isArray(data) ? data : [];
        total = list.length;
      }
      // 클라이언트 페이지네이션
      const start = (S.home.latest_page - 1) * S.home.latest_size;
      const end = start + S.home.latest_size;
      list = list.slice(start, end);
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
  // If query cleared → restore home sections
  if (!S.search.query || !S.search.query.trim()) {
    elSearchArea.style.display = 'none';
    elHomeSections.style.display = 'block';
    await bootstrapHome();
    return;
  }

  elHomeSections.style.display = 'none';
  elSearchArea.style.display = 'block';

  try {
    // helper to call search by status value
    const callSearch = async (status) => {
      const qs = new URLSearchParams();
      qs.set('q', S.search.query);
      if (status) qs.set('status', status);
      if (S.search.filters.location) qs.set('location', S.search.filters.location);
      if (S.search.filters.start_from) qs.set('start_from', S.search.filters.start_from);
      if (S.search.filters.start_to)   qs.set('start_to', S.search.filters.start_to);
      if (S.search.filters.end_from)   qs.set('end_from', S.search.filters.end_from);
      if (S.search.filters.end_to)     qs.set('end_to', S.search.filters.end_to);
      if (S.search.filters.sort_by)    qs.set('sort', S.search.filters.sort_by);
      if (S.search.filters.sort_dir)   qs.set('order', S.search.filters.sort_dir);
      qs.set('page', String(S.search.page));
      qs.set('size', String(S.search.size));
      return await fetchJSON(`/api/v1/challenges/search?${qs.toString()}`);
    };

    // Try current status; if empty, try active → completed as fallback
    let data = await callSearch(S.search.filters.status || 'recruiting');
    console.log('🔍 검색 API 응답:', data);
    
    // search 응답 구조에 맞게 처리
    let matched = Array.isArray(data.matched_challenges) ? data.matched_challenges : [];
    let rec = Array.isArray(data.recommended_by_tag_challenges) ? data.recommended_by_tag_challenges : [];

    if (matched.length === 0 && rec.length === 0) {
      const fallbacks = ['active', 'completed'];
      for (const st of fallbacks) {
        const d2 = await callSearch(st);
        const m2 = Array.isArray(d2.matched_challenges) ? d2.matched_challenges : [];
        const r2 = Array.isArray(d2.recommended_by_tag_challenges) ? d2.recommended_by_tag_challenges : [];
        if (m2.length || r2.length) { data = d2; matched = m2; rec = r2; break; }
      }
      // Final safety: client-side title contains fallback across all public challenges
      if (matched.length === 0 && rec.length === 0) {
        try {
          const all = await fetchJSON('/api/v1/challenges');
          const arr = Array.isArray(all?.items) ? all.items : (Array.isArray(all) ? all : []);
          const q = S.search.query.trim();
          const filt = arr.filter(ch => (ch?.title || '').toLowerCase().includes(q.toLowerCase()));
          matched = filt;
        } catch (_) {}
      }
    }
    console.log('🔍 처리된 데이터:', {matched_count: matched.length, rec_count: rec.length});
    
    // 검색 분석 결과 로깅 (디버깅용) 
    if (data.predicted_tag && S.search.query) {
      console.log('🔍 검색 분석:', {
        query: S.search.query,
        predicted_tag: data.predicted_tag,
        predicted_score: data.predicted_score
      });
      
      // 검색 분석 결과가 있지만 결과가 없는 경우 추가 정보 제공
      if (matched.length === 0 && rec.length === 0) {
        console.log('💡 검색 개선 제안: 다른 키워드를 시도해보세요.');
        if (data.predicted_tag) {
          console.log('🏷️ 예측된 태그:', `${data.predicted_tag} (${(data.predicted_score*100).toFixed(1)}%)`);
        }
      }
    }
    
    S.search.list = matched;
    S.search.total = matched.length;
    S.search.recommendations = rec;

    // 렌더 (팀원 코드 스타일)
    if (matched.length === 0) {
      elSearchGrid.innerHTML = "";
      elSearchEmpty.style.display = "block";
      elSearchEmpty.textContent = S.search.query ? `'${S.search.query}'와(과) 일치하는 챌린지가 없습니다.` : "검색어와 일치하는 챌린지가 없습니다.";
    } else {
      elSearchEmpty.style.display = "none";
      elSearchGrid.innerHTML = renderCardList(matched.slice(0, 8)); // 4×2
    }

    // 추천 섹션 처리 (태그 기반 매칭)
    console.log('🔍 추천 처리:', {rec_length: rec.length, rec_data: rec});
    if (rec.length === 0) {
      elRecGrid.innerHTML = "";
      elRecEmpty.style.display = "block";
      elRecEmpty.textContent = "추천할 챌린지가 없습니다.";
      console.log('❌ 추천 챌린지 없음');
    } else {
      elRecEmpty.style.display = "none";
      const html = renderCardList(rec.slice(0, 8));
      elRecGrid.innerHTML = html;
      console.log(`🎯 태그 기반 추천 ${rec.length}개 표시됨`, html.substring(0, 100) + '...');
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
  const cover = ch.cover_image_url || ch.cover_image || ch.thumbnail || '';
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
