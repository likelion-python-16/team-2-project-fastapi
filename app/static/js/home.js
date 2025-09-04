// ===== Config =====
const API_HOME = "/api/v1/home/sections";
const API_FOLLOWED = "/api/v1/follow/followed-challenges";
const API_SEARCH = "/api/v1/challenges/search";
const PAGE_SIZE_LATEST = 12;  // 최신은 12개(3×4)
const PAGE_SIZE_SEARCH = 10;  // 서버 페이지 사이즈(그대로)

// ===== State =====
let latestPage = 1;
let searchPage = 1;
let lastQuery = "";
let searchActive = false;

// 로그인 간단 체크 (localStorage 또는 sessionStorage)
function getToken(){
  try{ return localStorage.getItem("access_token") || sessionStorage.getItem("access_token") || ""; }
  catch{ return ""; }
}
let token = getToken();
let isLoggedIn = !!token;

// 쿠키 세션 확인 (토큰 없어도 로그인 상태일 수 있음)
async function ensureSessionFlag() {
  if (isLoggedIn) return; // 토큰 로그인 이미 OK
  try {
    const r = await fetch('/api/v1/users/me', { credentials: 'include' });
    if (r.ok) isLoggedIn = true; // 쿠키 로그인도 인정
  } catch(_) {}
}

// ===== Utils =====
function el(id){ return document.getElementById(id); }
function fmtDate(d){
  if(!d) return "-";
  const x = new Date(d);
  if (Number.isNaN(x.getTime())) return d;
  return x.getFullYear()+"-"+String(x.getMonth()+1).padStart(2,"0")+"-"+String(x.getDate()).padStart(2,"0");
}
function feeBadge(ch){
  const paid = (ch.fee && ch.fee>0) || (ch.participation_fee && ch.participation_fee>0);
  return '<span class="badge '+(paid? 'paid':'free')+'">'+(paid? '유료':'무료')+'</span>';
}
function statusBadge(k){
  const map = { recruiting:"모집중", active:"진행중", completed:"완료", cancelled:"취소" };
  const cls = k==="recruiting" ? "ok" : (k==="active"?"warn":"");
  return '<span class="badge '+cls+'">'+(map[k]||k)+'</span>';
}
function thumb(url){
  return url ? '<img class="thumb" src="'+url+'" alt="">' : '<div class="thumb"></div>';
}
function card(ch){
  return [
    '<div class="card">',
      thumb(ch.thumbnail_url),
      '<div class="card-body">',
        '<div class="title">', (ch.title||''), '</div>',
        '<div class="meta">',
          '<span class="chip">등록일 ', fmtDate(ch.created_at || ch.start_date), '</span>',
          '<span class="chip">기간 ', fmtDate(ch.start_date),' ~ ', fmtDate(ch.end_date), '</span>',
          '<span class="chip">총 ', (ch.total_rounds ?? '-'), '회차</span>',
        '</div>',
        '<div class="meta" style="margin-top:6px">',
          statusBadge(ch.status), ' ', feeBadge(ch),
        '</div>',
      '</div>',
    '</div>'
  ].join('');
}
function renderGrid(containerId, list){
  el(containerId).innerHTML = (list||[]).map(card).join("") || "";
}
function renderEmpty(containerId, text){
  const root = el(containerId);
  root.textContent = text;
  root.style.display = "block";
}

/* =========================
 *  Header: 프로필/로그인 UI
 * ========================= */
const DEFAULT_AVATAR = "/static/pictures/defaultprofile.jpeg";

async function fetchMe(tokenStr) {
  const init = tokenStr
    ? { headers: { Authorization: "Bearer " + tokenStr } }
    : { credentials: "include" }; // 쿠키 세션 확인
  try {
    const res = await fetch("/api/v1/users/me", init);
    if (!res.ok) throw new Error("unauthorized");
    return await res.json();
  } catch {
    return null;
  }
}
function safeAvatarUrl(user) {
  const raw = (user && (user.profile_image_url || user.profile_image || user.avatar_url || user.avatar)) || null;
  if (!raw || typeof raw !== "string" || !raw.trim()) return DEFAULT_AVATAR;
  return raw;
}

/* ▼▼▼ 로그인 상태별 트리거(UI) 구성 */
function buildLoggedOutMenu() {
  // 드롭다운 숨김 & 비우기
  const menu = el("profile-menu");
  if (menu) {
    menu.innerHTML = "";
    menu.style.display = "none";
  }

  // 동그라미 → 보라색 [로그인] 버튼
  const trigger = el("profile-trigger");
  trigger.classList.remove("avatar");
  trigger.classList.add("btn","primary");
  trigger.style.borderRadius = "10px";
  trigger.style.width = "auto";
  trigger.style.height = "38px";
  trigger.style.padding = "0 14px";
  trigger.title = "로그인";
  trigger.textContent = "로그인";
  trigger.onclick = function(e){
    e.preventDefault();
    location.href = "/login";
  };

  // 혹시 남아있을 이미지/텍스트 숨김
  const img = document.getElementById("profile-img");
  const txt = document.getElementById("profile-text");
  if (img) img.style.display = "none";
  if (txt) txt.style.display = "none";
}

function buildLoggedInMenu(user) {
  const name = (user && (user.name || user.username)) || "나";
  const menu = el("profile-menu");
  // 메뉴 내용만 구성(표시는 CSS .dropdown.open 이 담당)
  menu.innerHTML = [
    '<div class="dropdown-item" style="cursor:default"><strong>', name ,'</strong></div>',
    '<div class="divider"></div>',
    '<a class="dropdown-item" href="/me">마이페이지</a>',
    '<a class="dropdown-item" href="/profile">프로필 설정</a>',
    '<a class="dropdown-item" href="/account/edit">회원정보 수정</a>',
    '<div class="divider"></div>',
    '<button id="logout-btn" class="dropdown-item" type="button">로그아웃</button>'
  ].join("");

  // 버튼 → 동그란 아바타
  const trigger = el("profile-trigger");
  trigger.onclick = null; // 로그인 상태는 토글만
  trigger.classList.remove("btn","primary");
  trigger.classList.add("avatar");
  trigger.style.borderRadius = "50%";
  trigger.style.width = "36px";
  trigger.style.height = "36px";
  trigger.style.padding = "0";
  trigger.title = name;

  // 아바타 이미지 DOM
  trigger.innerHTML = [
    '<img id="profile-img" alt="avatar" style="display:none;width:100%;height:100%;object-fit:cover;" />',
    '<span id="profile-text" style="display:none"></span>'
  ].join("");
  const img = el("profile-img");
  const txt = el("profile-text");
  img.src = safeAvatarUrl(user);
  img.onload  = function(){ img.style.display = "block"; if (txt) txt.style.display = "none"; };
  img.onerror = function(){ img.src = DEFAULT_AVATAR; img.style.display = "block"; if (txt) txt.style.display = "none"; };

  const lo = document.getElementById("logout-btn");
  if (lo) lo.addEventListener("click", function(){
    try{
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("remember_login");
      sessionStorage.removeItem("access_token");
      sessionStorage.removeItem("refresh_token");
    }catch(_){ }
    location.href = "/login";
  });
}

/* 드롭다운 토글(클릭) + 호버(진입/이탈) 둘 다 지원 */
function initProfileDropdown(enable) {
  const dd = el("profile-dd");
  const trigger = el("profile-trigger");
  const menu = el("profile-menu");
  if (!dd || !trigger || !menu) return;

  // 항상 초기 상태는 닫힘
  dd.classList.remove("open");

  // 기존 리스너 초기화용(중복 방지)
  trigger.onmouseenter = null;
  trigger.onmouseleave = null;
  trigger.onclick = trigger.onclick || null;
  menu.onmouseenter = null;
  menu.onmouseleave = null;
  document.removeEventListener("__outsideClickHandler__", window.__outsideClickHandler || (()=>{}));

  if (!enable) return;

  let hoverTimer = null;
  let isHovering = false;

  function openDD(){ dd.classList.add("open"); }
  function closeDD(){ dd.classList.remove("open"); }

  // 클릭으로 토글
  trigger.addEventListener("click", function(e){
    e.stopPropagation();
    dd.classList.toggle("open");
  });

  // 바깥 클릭 시 닫기
  window.__outsideClickHandler = function(e){
    if (!dd.contains(e.target)) closeDD();
  };
  document.addEventListener("click", window.__outsideClickHandler);

  // 호버로 열기(바로 열기)
  trigger.onmouseenter = function(){
    isHovering = true;
    if (hoverTimer) { clearTimeout(hoverTimer); hoverTimer = null; }
    openDD();
  };
  // 메뉴/트리거 둘 다에서 벗어나면 약간의 딜레이 후 닫기
  function scheduleClose(){
    if (hoverTimer) clearTimeout(hoverTimer);
    hoverTimer = setTimeout(function(){
      if (!isHovering) closeDD();
    }, 180);
  }
  trigger.onmouseleave = function(){
    isHovering = false;
    scheduleClose();
  };
  menu.onmouseenter = function(){
    isHovering = true;
    if (hoverTimer) { clearTimeout(hoverTimer); hoverTimer = null; }
  };
  menu.onmouseleave = function(){
    isHovering = false;
    scheduleClose();
  };
}

async function initProfileUI() {
  const t = getToken();
  if (!t) {
    buildLoggedOutMenu();
    initProfileDropdown(false);
    return;
  }
  const me = await fetchMe(t);
  if (!me) {
    localStorage.removeItem("access_token");
    buildLoggedOutMenu();
    initProfileDropdown(false);
    return;
  }
  buildLoggedInMenu(me);
  initProfileDropdown(true);
}

// ===== Filters toggle =====
function setupFilters(){
  const tgl = el("filters-toggle");
  const panel = el("filters-panel");
  if (!tgl || !panel) return;
  tgl.addEventListener("click", function(){
    const open = panel.classList.toggle("open");
    tgl.classList.toggle("open", open);
    tgl.setAttribute("aria-expanded", open ? "true" : "false");
  });
}

// ===== Prev/Next pagination =====
function makePrevNext(rootId, page, hasPrev, hasNext, onPrev, onNext){
  const root = el(rootId);
  root.innerHTML = "";
  const prev = document.createElement("button");
  prev.className = "page-btn";
  prev.textContent = "이전";
  prev.disabled = !hasPrev;
  prev.addEventListener("click", function(){ onPrev(); });

  const next = document.createElement("button");
  next.className = "page-btn";
  next.textContent = "다음";
  next.disabled = !hasNext;
  next.addEventListener("click", function(){ onNext(); });

  root.appendChild(prev);
  const label = document.createElement("span");
  label.style.display = "inline-flex";
  label.style.alignItems = "center";
  label.style.padding = "0 8px";
  label.style.fontWeight = "600";
  label.textContent = "페이지 "+page;
  root.appendChild(label);
  root.appendChild(next);
}

// ===== Home sections =====
async function loadHomeSections(){
  const rlr = el("rec-login-required");
  const flr = el("follow-login-required");
  if (rlr) rlr.style.display = isLoggedIn ? "none" : "block";
  if (flr) flr.style.display = isLoggedIn ? "none" : "block";

  // 최신/추천(홈 섹션)도 로그인 시 토큰 또는 쿠키로 호출
  token = getToken(); 
  isLoggedIn = !!token || isLoggedIn;

  const homeUrl = new URL(API_HOME, window.location.origin);
  homeUrl.searchParams.set("latest_page", String(latestPage));
  homeUrl.searchParams.set("latest_page_size", String(PAGE_SIZE_LATEST));

  const homeInit = token
    ? { headers: { Authorization: "Bearer " + token } }
    : { credentials: "include" };

  const res = await fetch(homeUrl.toString(), homeInit);
  if(!res.ok){
    el("rec-list").innerHTML = "";
    el("latest-list").innerHTML = "";
    el("latest-pagination").innerHTML = "";
    return;
  }
  const data = await res.json();

  const rec = Array.isArray(data.recommended)? data.recommended : [];
  renderGrid("rec-list", rec.slice(0,6)); // 6개(3x2)

  if(data.recommended_notice && isLoggedIn){
    const n = el("rec-notice");
    if (n){ n.textContent = data.recommended_notice; n.style.display = "block"; }
  }else{
    const n = el("rec-notice");
    if (n) n.style.display = "none";
  }

  // 팔로우 API도 토큰 or 쿠키
  if(isLoggedIn){
    try{
      const followedInit = token
        ? { headers: { Authorization: "Bearer " + token } }
        : { credentials: "include" };
      const fr = await fetch(API_FOLLOWED, followedInit);
      if(fr.ok){
        const fl = await fr.json();
        renderGrid("follow-list", (fl||[]).slice(0,6));
      }else{
        el("follow-list").innerHTML = "";
      }
    }catch{ el("follow-list").innerHTML = ""; }
  } else {
    el("follow-list").innerHTML = "";
  }

  const latest = Array.isArray(data.latest)? data.latest : [];
  renderGrid("latest-list", latest); // 12개(4열×3줄)

  const hasPrev = latestPage > 1;
  const hasNext  = !!data.latest_has_next;
  makePrevNext(
    "latest-pagination",
    latestPage,
    hasPrev,
    hasNext,
    function(){ if(hasPrev){ latestPage--; loadHomeSections(); } },
    function(){ if(hasNext){ latestPage++; loadHomeSections(); } }
  );
}

// ===== Search flow =====
async function runSearch(page){
  if (page === undefined) page = 1;
  searchActive = true;
  el("home-sections").style.display = "none";
  el("search-area").style.display = "block";

  const q = (el("search-input").value||"").trim();
  lastQuery = q;
  const status = el("f-status").value || "recruiting";
  const sf = el("f-sf").value || "";
  const st = el("f-st").value || "";
  const ef = el("f-ef").value || "";
  const et = el("f-et").value || "";
  const sortBy = el("f-sortby").value || "created_at";
  const sortDir = el("f-sortdir").value || "desc";

  const u = new URL(API_SEARCH, window.location.origin);
  u.searchParams.set("q", q);
  u.searchParams.set("page", String(page));
  u.searchParams.set("page_size", String(PAGE_SIZE_SEARCH));
  u.searchParams.set("status", status);
  if(sf) u.searchParams.set("start_from", sf);
  if(st) u.searchParams.set("start_to", st);
  if(ef) u.searchParams.set("end_from", ef);
  if(et) u.searchParams.set("end_to", et);
  u.searchParams.set("sort_by", sortBy);
  u.searchParams.set("sort_dir", sortDir);

  const res = await fetch(u.toString());
  if(!res.ok){
    el("search-grid").innerHTML = "";
    el("rec-grid").innerHTML = "";
    renderEmpty("search-empty", "검색 중 오류가 발생했습니다.");
    el("rec-empty").style.display = "none";
    el("search-pagination").innerHTML = "";
    return;
  }
  const data = await res.json();
  const matched = Array.isArray(data.matched_challenges)? data.matched_challenges : [];
  const rec = Array.isArray(data.recommended_by_tag_challenges)? data.recommended_by_tag_challenges : [];

  if(matched.length===0){
    el("search-grid").innerHTML = "";
    el("search-empty").style.display = "block";
    el("search-empty").textContent = q ? '‘'+q+'’와(과) 일치하는 챌린지가 없습니다.' : "검색어와 일치하는 챌린지가 없습니다.";
  }else{
    el("search-empty").style.display = "none";
    renderGrid("search-grid", matched.slice(0,8)); // 4×2
  }

  if(rec.length===0){
    el("rec-grid").innerHTML = "";
    el("rec-empty").style.display = "block";
  }else{
    el("rec-empty").style.display = "none";
    renderGrid("rec-grid", rec.slice(0,8));
  }

  const hasPrev = page > 1;
  const hasNext = matched.length === PAGE_SIZE_SEARCH;
  makePrevNext(
    "search-pagination",
    page,
    hasPrev,
    hasNext,
    function(){ if(hasPrev){ searchPage = page-1; runSearch(searchPage); } },
    function(){ if(hasNext){ searchPage = page+1; runSearch(searchPage); } }
  );
}

// ===== Events & Init =====
function setupSearchForm(){
  const form = el("search-form");
  if (form){
    form.addEventListener("submit", function(e){
      e.preventDefault();
      searchPage = 1;
      runSearch(1);
    });
  }
  const reset = el("search-reset");
  if (reset){
    reset.addEventListener("click", function(){
      el("search-input").value = "";
      el("f-status").value = "recruiting";
      el("f-sf").value = "";
      el("f-st").value = "";
      el("f-ef").value = "";
      el("f-et").value = "";
      el("f-sortby").value = "created_at";
      el("f-sortdir").value = "desc";
      searchActive = false;
      el("search-area").style.display = "none";
      el("home-sections").style.display = "block";
      loadHomeSections();
    });
  }
}

document.addEventListener("DOMContentLoaded", async function(){
  // 생성 버튼: 서버로 로그인 실 확인
  const btn = document.getElementById("create-challenge-btn");
  if (btn) {
    btn.addEventListener("click", async function(e){
      e.preventDefault();
      try {
        const r = await fetch('/api/v1/users/me', {
          credentials: 'include',
          cache: 'no-store'
        });
        if (r.ok) { location.href = '/pages/challenges/create'; return; }
      } catch(_) {}
      alert("로그인이 필요합니다 🙏");
      location.href = "/login";
    });
  }

  await ensureSessionFlag();   // 쿠키 로그인도 인정
  await initProfileUI();       // fetchMe가 쿠키도 보므로 정상
  setupFilters();
  setupSearchForm();
  loadHomeSections();
});
