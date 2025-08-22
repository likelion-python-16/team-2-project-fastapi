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

// 로그인 간단 체크
const token = localStorage.getItem("access_token");
const isLoggedIn = !!token;

// ===== Utils =====
function el(id){ return document.getElementById(id); }
function fmtDate(d){
  if(!d) return "-";
  const x = new Date(d);
  if (Number.isNaN(x.getTime())) return d;
  return `${x.getFullYear()}-${String(x.getMonth()+1).padStart(2,"0")}-${String(x.getDate()).padStart(2,"0")}`;
}
function feeBadge(ch){
  const paid = (ch.fee && ch.fee>0) || (ch.participation_fee && ch.participation_fee>0);
  return `<span class="badge ${paid? 'paid':'free'}">${paid? '유료':'무료'}</span>`;
}
function statusBadge(k){
  const map = { recruiting:"모집중", active:"진행중", completed:"완료", cancelled:"취소" };
  const cls = k==="recruiting" ? "ok" : (k==="active"?"warn":"");
  return `<span class="badge ${cls}">${map[k]||k}</span>`;
}
function thumb(url){
  return url ? `<img class="thumb" src="${url}" alt="">` : `<div class="thumb"></div>`;
}
function card(ch){
  return `
    <div class="card">
      ${thumb(ch.thumbnail_url)}
      <div class="card-body">
        <div class="title">${ch.title}</div>
        <div class="meta">
          <span class="chip">등록일 ${fmtDate(ch.created_at || ch.start_date)}</span>
          <span class="chip">기간 ${fmtDate(ch.start_date)} ~ ${fmtDate(ch.end_date)}</span>
          <span class="chip">총 ${ch.total_rounds ?? '-'}회차</span>
        </div>
        <div class="meta" style="margin-top:6px">
          ${statusBadge(ch.status)} ${feeBadge(ch)}
        </div>
      </div>
    </div>
  `;
}
function renderGrid(containerId, list){
  el(containerId).innerHTML = list.map(card).join("") || "";
}
function renderEmpty(containerId, text){
  const root = el(containerId);
  root.textContent = text;
  root.style.display = "block";
}

// ===== Header: profile dropdown =====
function setupProfile(){
  const trigger = el("profile-trigger");
  const dd = el("profile-dd");
  const menu = el("profile-menu");
  if(isLoggedIn){
    menu.innerHTML = `
      <div class="dropdown-item"><span>마이페이지</span></div>
      <div class="divider"></div>
      <div id="logout-btn" class="dropdown-item"><span>로그아웃</span></div>
    `;
  }else{
    menu.innerHTML = `
      <a class="dropdown-item" href="/login">로그인</a>
      <a class="dropdown-item" href="/signup">회원가입</a>
    `;
  }
  trigger.addEventListener("click", ()=> dd.classList.toggle("open"));
  document.addEventListener("click", (e)=>{ if(!dd.contains(e.target)) dd.classList.remove("open"); });
  const lo = el("logout-btn");
  if(lo){ lo.addEventListener("click", ()=>{ localStorage.removeItem("access_token"); location.reload(); }); }
  el("home-logo").addEventListener("click", ()=>{
    searchActive = false;
    el("search-area").style.display = "none";
    el("home-sections").style.display = "block";
    el("search-input").value = "";
    loadHomeSections();
  });
}

// ===== Filters toggle =====
function setupFilters(){
  const tgl = el("filters-toggle");
  const panel = el("filters-panel");
  tgl.addEventListener("click", ()=>{
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
  prev.addEventListener("click", ()=> onPrev());

  const next = document.createElement("button");
  next.className = "page-btn";
  next.textContent = "다음";
  next.disabled = !hasNext;
  next.addEventListener("click", ()=> onNext());

  root.appendChild(prev);
  const label = document.createElement("span");
  label.style.display = "inline-flex";
  label.style.alignItems = "center";
  label.style.padding = "0 8px";
  label.style.fontWeight = "600";
  label.textContent = `페이지 ${page}`;
  root.appendChild(label);
  root.appendChild(next);
}

// ===== Home sections =====
async function loadHomeSections(){
  el("rec-login-required").style.display = isLoggedIn ? "none" : "block";
  el("follow-login-required").style.display = isLoggedIn ? "none" : "block";

  const url = new URL(API_HOME, window.location.origin);
  url.searchParams.set("latest_page", String(latestPage));
  url.searchParams.set("latest_page_size", String(PAGE_SIZE_LATEST));
  const res = await fetch(url.toString(), {headers: token? {Authorization:`Bearer ${token}`} : {}});
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
    n.textContent = data.recommended_notice;
    n.style.display = "block";
  }else{
    el("rec-notice").style.display = "none";
  }

  if(isLoggedIn){
    try{
      const fr = await fetch(API_FOLLOWED, {headers:{Authorization:`Bearer ${token}`}});
      if(fr.ok){
        const fl = await fr.json();
        renderGrid("follow-list", (fl||[]).slice(0,6)); // 6개(3x2)
      }else{
        el("follow-list").innerHTML = "";
      }
    }catch{ el("follow-list").innerHTML = ""; }
  }else{
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
    ()=>{ if(hasPrev){ latestPage--; loadHomeSections(); } },
    ()=>{ if(hasNext){ latestPage++; loadHomeSections(); } }
  );
}

// ===== Search flow =====
async function runSearch(page=1){
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
    el("search-empty").textContent = q ? `‘${q}’와(과) 일치하는 챌린지가 없습니다.` : "검색어와 일치하는 챌린지가 없습니다.";
  }else{
    el("search-empty").style.display = "none";
    // ✅ 검색 결과도 4열에 맞춰 최대 8개(4×2)
    renderGrid("search-grid", matched.slice(0,8));
  }

  if(rec.length===0){
    el("rec-grid").innerHTML = "";
    el("rec-empty").style.display = "block";
  }else{
    el("rec-empty").style.display = "none";
    // 이미 ‘이런 챌린지는 어떠세요?’도 4열×2로 8개
    renderGrid("rec-grid", rec.slice(0,8));
  }

  const hasPrev = page > 1;
  const hasNext = matched.length === PAGE_SIZE_SEARCH;
  makePrevNext(
    "search-pagination",
    page,
    hasPrev,
    hasNext,
    ()=>{ if(hasPrev){ searchPage = page-1; runSearch(searchPage); } },
    ()=>{ if(hasNext){ searchPage = page+1; runSearch(searchPage); } }
  );
}

// ===== Events =====
function setupSearchForm(){
  el("search-form").addEventListener("submit", (e)=>{
    e.preventDefault();
    searchPage = 1;
    runSearch(1);
  });
  el("search-reset").addEventListener("click", ()=>{
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

// ===== Init =====
document.addEventListener("DOMContentLoaded", ()=>{
  setupProfile();
  setupFilters();
  setupSearchForm();
  loadHomeSections();
});