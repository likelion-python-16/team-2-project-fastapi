/* ===== 공통 유틸 ===== */
    const API = ""; // same-origin
    const qs = id => document.getElementById(id);
    const $ = sel => document.querySelector(sel);
    const $$ = sel => Array.from(document.querySelectorAll(sel));
    const urlp = new URLSearchParams(location.search);
    const GUEST = urlp.get("guest")==="1";
    const VIEW_USER_ID = (function(){
      if (typeof window.MYPAGE_VIEW_USER_ID !== 'undefined' && window.MYPAGE_VIEW_USER_ID !== null) {
        const n = Number(window.MYPAGE_VIEW_USER_ID);
        return Number.isFinite(n)? n : null;
      }
      const attr = document.body?.dataset?.viewUserId;
      if (attr && attr !== '') {
        const n = Number(attr);
        return Number.isFinite(n)? n : null;
      }
      return null;
    })();
    const isOtherView = Number.isInteger(VIEW_USER_ID);

    function toast(msg){ const z=qs("toasts"); const t=document.createElement("div"); t.className="toast"; t.textContent=msg; z.appendChild(t); setTimeout(()=>t.remove(), 3200); }

    // micro-anim: number count-up
    function countTo(el, target, ms=600){
      if(!el) return;
      const safeNum = (v)=>{ try{ return Number(String(v).replace(/[^0-9-]/g,''))||0; }catch{ return 0; } };
      const start = safeNum(el.textContent);
      const end = Number(target)||0;
      const t0 = performance.now();
      const ease = t=> 1 - Math.pow(1-t,3);
      function step(now){
        const p = Math.min(1, (now - t0) / ms);
        const val = Math.round(start + (end - start) * ease(p));
        try{ el.textContent = val.toLocaleString('ko-KR'); }catch{ el.textContent = String(val); }
        if(p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    }

    // reveal-on-scroll
    function initReveal(){
      const els = Array.from(document.querySelectorAll('.card, .hero, .table-wrap'));
      els.forEach(el=> el.classList.add('reveal'));
      const io = new IntersectionObserver((entries)=>{
        entries.forEach(en=>{
          if(en.isIntersecting){ en.target.classList.add('in'); io.unobserve(en.target); }
        });
      }, { rootMargin: '0px 0px -10% 0px', threshold: 0.08 });
      els.forEach(el=> io.observe(el));
    }

    function token(){
      try{const t=localStorage.getItem("access_token"); if(t) return t;}catch{}
      try{const s=sessionStorage.getItem("access_token"); if(s) return s;}catch{}
      const m=document.cookie.match(/(?:^|;)\s*access_token=([^;]+)/); return m?decodeURIComponent(m[1]):null;
    }

    async function safeText(r){ try{ return await r.text(); }catch{ return ""; } }
    async function safeErr(r){
      const txt = await safeText(r);
      try{ const j = JSON.parse(txt); return j.detail || j.message || txt || `HTTP ${r.status}`; }
      catch{ return txt || `HTTP ${r.status}`; }
    }

    // fetch helpers
    async function jget(path){
      const h={"Content-Type":"application/json"};
      const t=token(); if(t) h["Authorization"]="Bearer "+t;
      const r=await fetch(API+path,{headers:h, credentials:"include"});
      if(r.status===401){ if(GUEST) return null; location.href="/login"; return null; }
      if(!r.ok) throw new Error(await safeErr(r));
      return await r.json();
    }
    async function jpatch(path, body){
      const h={"Content-Type":"application/json"};
      const t=token(); if(t) h["Authorization"]="Bearer "+t;
      const r=await fetch(API+path,{method:"PATCH", headers:h, body:JSON.stringify(body), credentials:"include"});
      if(r.status===401){ if(GUEST) return null; location.href="/login"; return null; }
      if(!r.ok) throw new Error(await safeErr(r));
      return await r.json();
    }
    async function jpost(path, body){
      const h={"Content-Type":"application/json"};
      const t=token(); if(t) h["Authorization"]="Bearer "+t;
      const r=await fetch(API+path,{method:"POST", headers:h, body: body? JSON.stringify(body): undefined, credentials:"include"});
      if(r.status===401){ if(GUEST) return null; location.href="/login"; return null; }
      if(!r.ok) throw new Error(await safeErr(r));
      return await r.json();
    }
    async function uploadFile(file){
      const t=token(); const fm=new FormData(); fm.append("file", file);
      const r = await fetch("/api/v1/files/profile-image", {method:"POST", headers: t?{"Authorization":"Bearer "+t}:{}, body: fm, credentials:"include"});
      if(!r.ok) throw new Error(await safeErr(r));
      return await r.json();
    }

    /* ===== 좌측 네비 ===== */
    qs("btn_nav_toggle").onclick = () => qs("sidenav").classList.toggle("collapsed");
    $$(".nav .item").forEach(it=> it.onclick = () => {
      const anchor = it.getAttribute("data-jump");
      if(anchor){ document.querySelector(anchor)?.scrollIntoView({behavior:"smooth", block:"start"}); }
    });

    // Header shadow on scroll
    (function(){
      const hd = document.querySelector('.header');
      const onScroll = ()=>{ if(!hd) return; hd.classList.toggle('scrolled', window.scrollY > 4); };
      window.addEventListener('scroll', onScroll, {passive:true}); onScroll();
    })();

    // Nav highlight by section in view — disabled
(function(){ /* no-op */ })();

    /* (탭 제거) 단일 My Profile 화면만 사용 */

    /* ===== 상태 ===== */
    const state = {
      following:{skip:0,limit:10,total:0, list:[]},
      followers:{skip:0,limit:10,total:0, list:[]},
      challenges:{page:1,pageSize:5,total:0, list:[]},
      payments:{paid:[], refund:[], paidPage:1, refundPage:1, pageSize:5},
      reviews:{items:[], page:1, pageSize:5},
      allTags:[],
      selectedTagIds:new Set(),
      selectedTags:[],
      my:{},
    };

    // 섹션 공개 설정
    const visInputs = {
      followers: qs("vis_followers"),
      challenges: qs("vis_challenges"),
      interests: qs("vis_interests"),
      reviews: qs("vis_reviews"),
    };
    const visRows = {
      followers: qs("vis_row_followers"),
      challenges: qs("vis_row_challenges"),
      interests: qs("vis_row_interests"),
    };

    function applyVisibilityToCards(v){
      if(!isOtherView) return; // 내 화면은 항상 전체 표시
      const map = Object.assign({profile:true,followers:true,challenges:true,interests:true,reviews:true}, v||{});
      const cards = document.querySelectorAll('[data-section]');
      cards.forEach(card=>{
        const key = card.getAttribute('data-section');
        // 프로필은 항상 공개
        if(key === 'profile') { card.style.display = ''; return; }
        if(key === 'payments' && isOtherView){ card.style.display='none'; return; }
        card.style.display = (map[key]===false) ? 'none' : '';
      });

      // 네비 항목도 숨겨진 섹션은 감춤
      document.querySelectorAll('.nav .item[data-jump]').forEach(it=>{
        const anchor = it.getAttribute('data-jump');
        const target = anchor ? document.querySelector(anchor) : null;
        if(target){ it.style.display = (target.style.display === 'none') ? 'none' : ''; }
      });
    }

    // ===== 채팅 & 팔로우 (상대 프로필일 때만 표시) =====
    (function(){
      if(!isOtherView) return;
      const bar = document.getElementById('chat_action_bar');
      const btn = document.getElementById('btn_chat_with_user');
      const btnFollow = document.getElementById('btn_follow_user');
      const btnUnfollow = document.getElementById('btn_unfollow_user');
      if(!bar || !btn) return;
      const t = token();
      if(!t){ bar.style.display='none'; return; }
      bar.style.display='flex';
      btn.addEventListener('click', async ()=>{
        try{
          const res = await jpost(`/api/v1/chat/rooms/with/${VIEW_USER_ID}`);
          const rid = res?.room_id;
          if(rid){ window.location.href = `/chat/rooms/${rid}`; }
          else { throw new Error('방을 생성할 수 없습니다'); }
        }catch(e){ alert(e?.message||e||'채팅 시작에 실패했습니다'); }
      });

      // 팔로우 상태 확인 및 토글 바인딩
      async function refreshFollowState(){
        try{
          const r = await jget('/api/v1/following/users');
          const ids = (r?.following_user_ids || []).map(n=>Number(n));
          const isFollowing = ids.includes(Number(VIEW_USER_ID));
          if(btnFollow) btnFollow.style.display = isFollowing ? 'none' : '';
          if(btnUnfollow) btnUnfollow.style.display = isFollowing ? '' : 'none';
        }catch(_){
          if(btnFollow) btnFollow.style.display = '';
          if(btnUnfollow) btnUnfollow.style.display = 'none';
        }
      }
      refreshFollowState();

      btnFollow?.addEventListener('click', async ()=>{
        try{
          await jpost(`/api/v1/follow/${VIEW_USER_ID}`);
          // 팔로워 수 +1 (낙관적)
          const el = document.getElementById('hero_followers');
          if(el){ const n = Number(el.textContent.replace(/[^0-9]/g,''))||0; el.textContent = (n+1).toString(); }
          // 즉시 토글
          if(btnFollow) btnFollow.style.display = 'none';
          if(btnUnfollow) btnUnfollow.style.display = '';
          refreshFollowState();
        }catch(e){ alert(e?.message||'팔로우 실패'); }
      });
      btnUnfollow?.addEventListener('click', async ()=>{
        try{
          const tkn = token();
          await fetch(`/api/v1/follow/${VIEW_USER_ID}`, {method:'DELETE', headers: tkn? {'Authorization': 'Bearer '+tkn} : {}, credentials:'include'});
          // 팔로워 수 -1 (낙관적)
          const el = document.getElementById('hero_followers');
          if(el){ const n = Number(el.textContent.replace(/[^0-9]/g,''))||0; el.textContent = Math.max(0,n-1).toString(); }
          // 즉시 토글
          if(btnFollow) btnFollow.style.display = '';
          if(btnUnfollow) btnUnfollow.style.display = 'none';
          refreshFollowState();
        }catch(e){ alert(e?.message||'언팔로우 실패'); }
      });
    })();

    async function loadVisibility(){
      try{
        if(isOtherView){
          const v = await jget(`/api/v1/users/${VIEW_USER_ID}/visibility`);
          // 타인 보기: 설정 UI 숨김 + 카드 표시 제어
          Object.values(visRows).forEach(r=>{ if(r) r.style.display='none'; });
          const btns = [qs('btn_edit_profile'), qs('btn_edit_tags2')];
          btns.forEach(b=>{ if(b) b.style.display='none'; });
          applyVisibilityToCards(v);
        }else{
          const v = await jget('/api/v1/users/me/visibility');
          // 토글 버튼 초기 상태 반영 + 핸들러 바인딩
          const setState = (btn, on)=>{
            if(!btn) return;
            btn.classList.toggle('on', !!on);
            btn.classList.toggle('off', !on);
            const lab = btn.querySelector('.label'); if(lab) lab.textContent = on ? '공개' : '비공개';
          };
          const bind = (key)=>{
            const btn = visInputs[key]; if(!btn) return;
            setState(btn, !!v[key]);
            btn.onclick = async ()=>{
              const next = !btn.classList.contains('on');
              try{ await jpatch('/api/v1/users/me/visibility', {[key]: next}); setState(btn, next); }
              catch(e){ toast('저장 실패: '+(e?.message||e)); }
            };
          };
          bind('followers'); bind('interests'); bind('challenges'); bind('reviews');
        }
      }catch(e){ /* noop */ }
    }

    /* ===== 프로필 UI 반영 ===== */
    function applyProfile(u){
      if(!u) return;
      state.my = u;
      // 상단 Public 영역 제거에 따라 My Profile 요소만 갱신
      qs("my_name").textContent   = u.name || "-";
      const heroNameEl = qs("hero_name"); if(heroNameEl) heroNameEl.textContent = u.name || u.username || "-";
      qs("my_phone").textContent  = isOtherView ? "비공개" : (u.phone || u.phone_number || "-");
      const home = u.home_region || u.region_living || "-";
      const active = u.active_region || u.region_active || "-";
      qs("my_home").textContent   = home;
      qs("my_active").textContent = active;
      if(qs("hero_home")) qs("hero_home").textContent = home;
      if(qs("hero_active")) qs("hero_active").textContent = active;
      const intro = (u.introduction || "").trim();
      qs("my_intro").textContent  = intro || "소개글이 없습니다.";
      if(qs("hero_intro")) qs("hero_intro").textContent = intro ? `“${intro}”` : "“소개글이 없습니다.”";

      const ms = (u.manner_score ?? u.manner ?? null);
      if(ms!=null){
        qs("my_manner").textContent    = ms;
      }
      if(u.total_points != null){
        try { qs("my_points").textContent = Number(u.total_points||0).toLocaleString('ko-KR'); } catch {}
      }
      const DEF = '/static/defaults/avatar-default.png';
      const raw = u.avatar_url || u.profile_image || '';
      const bust = (url)=> url ? (url + (url.includes('?')? '&':'?') + 'v=' + Date.now()) : DEF;
      const src = bust(raw);
      const setImg = (el)=>{ if(!el) return; el.onerror = ()=>{ el.src = DEF; }; el.src = src; };
      setImg(qs("avatar_preview"));
      setImg(qs("edit_avatar_preview"));
      setImg(qs("hero_avatar"));
    }

    /* ===== 데이터 로드 ===== */
    async function loadSummaryAndPoints(){
      if(isOtherView) return;
      try{
        const p = await jget("/api/v1/users/me/points?skip=0&limit=1");
        if(p){ countTo(qs("my_points"), p.current_points||0, 700); }
      }catch(e){}
    }

    async function loadProfile(){
      let u = null;
      if(isOtherView){
        try { u = await jget(`/api/v1/users/${VIEW_USER_ID}`); } catch(_){ }
      } else {
        try { u = await jget("/api/v1/users/me/profile"); } catch(_){ }
        if(!u){
          try { u = await jget("/api/v1/users/me"); } catch(_){ }
        }
      }
      if(u) applyProfile(u);
      return u;
    }

    async function loadChallenges(){
      try{
        let items = [];
        if(isOtherView){
          const res = await jget(`/api/v1/challenges/user/${VIEW_USER_ID}`);
          items = Array.isArray(res) ? res : (res?.items || []);
        } else {
          const q = new URLSearchParams({skip: String(state.challenges.skip), limit: String(state.challenges.limit)});
          const res = await jget("/api/v1/challenges?mine=true&"+q.toString());
          if(res) items = res.items || res || [];
        }

        // 실제 데이터만 표시 (더미 데이터 제거됨)

        const tbody2 = qs("tbl_challenges_my").querySelector("tbody");
        tbody2.innerHTML = "";
        (items||[]).forEach(ch=>{
          const s = (ch.start_at||ch.start_date||"").toString().slice(0,10);
          const e = (ch.end_at||ch.end_date||"").toString().slice(0,10);
          const tr = `<tr><td>${ch.title||"-"}</td><td>${s}</td><td>${e}</td></tr>`;
          tbody2.insertAdjacentHTML("beforeend", tr);
        });
      }catch(e){}
    }

    function renderChallengesPage(page){
      const st = state.challenges; const tbody = qs('tbl_challenges_my').querySelector('tbody');
      const ps = st.pageSize; const total = st.total; const pages = Math.max(1, Math.ceil(total/ps));
      st.page = Math.min(Math.max(1, page), pages);
      const start = (st.page-1)*ps; const slice = st.list.slice(start, start+ps);
      tbody.innerHTML = slice.map(ch=>{
        const s=(ch.start_at||ch.start_date||'').toString().slice(0,10);
        const e=(ch.end_at||ch.end_date||'').toString().slice(0,10);
        return `<tr><td>${ch.title||'-'}</td><td>${s}</td><td>${e}</td></tr>`;
      }).join('') || '<tr><td colspan="3">데이터 없음</td></tr>';
      const from = total? start+1:0; const to = Math.min(start+slice.length, total);
      qs('ch_info').textContent = `${from}-${to} / ${total}`;
      qs('ch_prev').disabled = (st.page<=1);
      qs('ch_next').disabled = (st.page>=pages);
    }

    /* ===== 관심 태그 ===== */
    async function loadAllTags(){
      try{
        const arr = await jget("/api/v1/tags/");
        state.allTags = Array.isArray(arr) ? arr : [];
      }catch(e){
        state.allTags = [];
        toast("태그 목록을 불러오지 못했습니다.");
      }
    }

    /* ===== 결제 내역 (프론트 전용) ===== */
    async function loadSpendSummary(){
      if(isOtherView){ const c = document.getElementById('my_sec_payments'); if(c) c.style.display='none'; return; }
      const paidEl = qs('summary_paid');
      const refundEl = qs('summary_refund');
      if(!paidEl || !refundEl) return;
      // prepare fade views
      paidEl.classList.add('fade-view','show');
      refundEl.classList.add('fade-view','hidden');
      const paidWrap = qs('table_paid_wrap');
      const refWrap = qs('table_refund_wrap');
      if(paidWrap) paidWrap.classList.add('fade-view','show');
      if(refWrap) refWrap.classList.add('fade-view','hidden');
      function swapFade(showEl, hideEl){
        if(!showEl || !hideEl) {
          console.log('swapFade 요소 없음:', showEl, hideEl);
          return;
        }
        console.log('swapFade 실행:', showEl.id, '←→', hideEl.id);
        hideEl.classList.remove('show');
        hideEl.style.display = 'none';  // 강제로 숨기기
        setTimeout(()=> hideEl.classList.add('hidden'), 220);
        showEl.classList.remove('hidden');
        showEl.style.display = 'block';  // 강제로 보이기
        requestAnimationFrame(()=> showEl.classList.add('show'));
      }
      try{
        const r = await jget('/api/v1/users/me/spend/summary?include_deposit=true');
        const paid = Number(r?.total_paid||0).toLocaleString('ko-KR');
        const ref  = Number(r?.total_refunded||0).toLocaleString('ko-KR');
        paidEl.textContent = paid + ' 원';
        refundEl.textContent = ref + ' 원';
      }catch(e){
        paidEl.textContent = '- 원';
        refundEl.textContent = '- 원';
      }
      const tabs = Array.from(document.querySelectorAll('#my_sec_payments .tab-mini'));
      console.log('탭 버튼들:', tabs);
      tabs.forEach(btn=>{
        btn.onclick = ()=>{
          console.log('탭 클릭됨:', btn.getAttribute('data-tab'));
          tabs.forEach(b=>b.classList.remove('active'));
          btn.classList.add('active');
          const k = btn.getAttribute('data-tab');
          const showPaid = (k==='paid');
          console.log('showPaid:', showPaid);
          if(showPaid){
            swapFade(paidEl, refundEl);
            swapFade(paidWrap, refWrap);
          }else{
            swapFade(refundEl, paidEl);
            swapFade(refWrap, paidWrap);
            console.log('환급 탭으로 전환 중...');
          }
          const paidSum = qs('paid_sum_line'); const refSum = qs('refund_sum_line');
          if(paidSum && refSum){
            paidSum.style.display = showPaid? '' : 'none';
            refSum.style.display = showPaid? 'none' : '';
          }
        };
      });

      // 하단 리스트 로딩
      try{
        const paidRes = await jget('/api/v1/users/me/payments?status=paid&skip=0&limit=50');
        const paidItems = Array.isArray(paidRes?.items)? paidRes.items : [];
        const pb = qs('paid_body');
        pb.innerHTML = paidItems.map(p=>{
          const ts=(p.created_at||'').toString().slice(0,10);
          const amt=(p.amount??0).toLocaleString('ko-KR');
          return `<tr><td class="mono">${ts}</td><td class="mono">${amt}</td><td>-</td><td>${p.status||''}</td></tr>`;
        }).join('') || '<tr><td colspan="4">데이터 없음</td></tr>';
        const paidSum = paidItems.reduce((a,b)=> a + (b.amount||0), 0);
      }catch(e){ qs('paid_body').innerHTML = '<tr><td colspan="4">불러오기 실패</td></tr>'; }

      try{
        console.log('환불 내역 API 호출 시작...');
        const refRes = await jget('/api/v1/users/me/refunds?skip=0&limit=50');
        console.log('환불 내역 API 응답:', refRes);
        const refItems = Array.isArray(refRes?.items)? refRes.items : [];
        const rb = qs('refund_body');
        rb.innerHTML = refItems.map(p=>{
          const ts=(p.created_at||'').toString().slice(0,10);
          const amt=(p.amount??0).toLocaleString('ko-KR');
          return `<tr><td class="mono">${ts}</td><td class="mono">${amt}</td><td>-</td><td>${p.status||''}</td></tr>`;
        }).join('') || '<tr><td colspan="4">데이터 없음</td></tr>';
        const refSum = refItems.reduce((a,b)=> a + (b.amount||0), 0);
        console.log('환급 합계 계산:', refSum);
        // 환급 합계를 summary에 반영
        const refundSummary = qs('summary_refund');
        if(refundSummary) {
          refundSummary.textContent = refSum.toLocaleString('ko-KR') + ' 원';
          console.log('환급 합계 UI 업데이트:', refundSummary.textContent);
        }
      }catch(e){ 
        console.error('환불 내역 로딩 실패:', e);
        qs('refund_body').innerHTML = '<tr><td colspan="4">불러오기 실패</td></tr>'; 
      }
    }

    /* ===== 리뷰 내역 (프론트 전용) ===== */
    async function loadReviews(){
      const tbody = qs('reviews_body'); if(!tbody) return;
      // 서버에 리뷰 API가 없을 수도 있으므로 graceful fallback
      try{
        const res = await jget('/api/v1/users/me/reviews?skip=0&limit=10');
        const items = Array.isArray(res?.items) ? res.items : [];
        if(items.length){
          tbody.innerHTML = items.map(r=>{
            const star='★'.repeat(Math.max(0,Math.min(5, r.rating||0)));
            return `<tr><td>${star}</td><td>${(r.content||'').slice(0,120)}</td></tr>`;
          }).join('');
          return;
        }
      }catch(_){
        // 데이터 로딩 실패시 빈 상태 표시
        tbody.innerHTML = '<tr><td colspan="2" style="text-align:center;color:#999;">리뷰 데이터가 없습니다.</td></tr>';
      }
    }

    /* ===== 팔로워/팔로잉 카운트 ===== */
    async function loadFollowCounts(){
      try{
        const base = isOtherView ? `/api/v1/users/${VIEW_USER_ID}` : `/api/v1/users/me`;
        const frs = await jget(`${base}/followers?skip=0&limit=1`).catch(()=>null);
        const fng = await jget(`${base}/following?skip=0&limit=1`).catch(()=>null);
        if(qs('hero_followers')) countTo(qs('hero_followers'), frs?.total ?? 0, 600);
        if(qs('hero_following')) countTo(qs('hero_following'), fng?.total ?? 0, 600);
      }catch(e){
        if(qs('hero_followers')) qs('hero_followers').textContent = '0';
        if(qs('hero_following')) qs('hero_following').textContent = '0';
      }
    }

    async function loadMyInterests(){
      try{
        const path = isOtherView ? `/api/v1/users/${VIEW_USER_ID}/interests` : "/api/v1/users/me/interests";
        const res = await jget(path);
        const ids = (res?.tag_ids || []).map(Number);
        state.selectedTagIds = new Set(ids);
        state.selectedTags = Array.isArray(res?.tags) ? res.tags : [];
        renderSelectedTags();
        renderSelectedBar();
      }catch(e){
        state.selectedTagIds = new Set();
        state.selectedTags = [];
        renderSelectedTags();
        renderSelectedBar();
        toast("관심 태그 조회 실패");
      }
    }

    function renderSelectedTags(){
      const el = qs("tag_zone_my");
      el.innerHTML = "";
      const tags = state.selectedTags || [];
      if(!tags.length){ el.innerHTML = `<span class="muted">선택된 태그가 없습니다.</span>`; return; }
      tags.forEach(t=>{
        const name = t.tag ?? t.name ?? t.title ?? String(t);
        el.insertAdjacentHTML("beforeend", `<span class="tag">${name}</span>`);
      });
    }

    /* 칩 토글 */
    function toggleTag(id){
      const sel = state.selectedTagIds;
      if(sel.has(id)){ sel.delete(id); }
      else{
        if(sel.size >= 10){ toast("태그는 최대 10개까지 선택할 수 있어요."); return; }
        sel.add(id);
      }
      const map = new Map((state.allTags||[]).map(t=>[Number(t.id), t]));
      state.selectedTags = Array.from(sel).map(i=> map.get(Number(i))).filter(Boolean);
      renderTagPool();
      renderSelectedBar();
    }

    function renderSelectedBar(){
      const bar = qs("tag_selected_bar");
      bar.innerHTML = "";
      if(!state.selectedTags.length){
        bar.innerHTML = `<span class="chips-help" style="margin:0">선택된 항목이 없습니다.</span>`;
        return;
      }
      state.selectedTags.forEach(t=>{
        const id = Number(t.id);
        const el = document.createElement("span");
        el.className = "chip selected";
        el.innerHTML = `${t.tag||t.name}<span class="x" data-id="${id}">×</span>`;
        el.querySelector(".x").onclick = (e)=>{ e.stopPropagation(); toggleTag(id); };
        bar.appendChild(el);
      });
    }

    function renderTagPool(){
      const pool = qs("tag_pool"); pool.innerHTML = "";
      const query = (qs("tag_search").value||"").toLowerCase();
      const selected = state.selectedTagIds;

      (state.allTags||[])
        .filter(t=>{
          const name=(t.tag||t.name||"").toLowerCase();
          return !query || name.includes(query);
        })
        .forEach(t=>{
          const id = Number(t.id);
          const chip = document.createElement("button");
          chip.type = "button";
          chip.className = "chip" + (selected.has(id) ? " selected" : "");
          chip.textContent = t.tag || t.name;
          chip.setAttribute("data-id", String(id));
          chip.onclick = ()=> toggleTag(id);
          pool.appendChild(chip);
        });
    }
    qs("tag_search").addEventListener("input", renderTagPool);

    // 저장 버튼: PATCH 보내고 재조회/화면갱신
    qs("tags_save").onclick = async ()=>{
      const btn = qs("tags_save");
      const ids = Array.from(state.selectedTagIds);
      if(ids.length > 10){ toast("태그는 최대 10개까지 선택할 수 있어요."); return; }

      btn.disabled = true;
      const orig = btn.textContent;
      btn.textContent = "저장 중...";
      try{
        const payload = { tag_ids: ids };                // ← 서버 스키마에 맞춤
        await jpatch("/api/v1/users/me/interests", payload);
        toast("관심 태그 저장 완료");

        // 최신 상태 재조회 & 반영
        await loadMyInterests();
      }catch(e){
        let msg = String(e?.message || e || "저장 실패");
        if(msg.startsWith("Traceback")) msg = "저장 중 서버 오류가 발생했습니다.";
        toast(msg);
      }finally{
        btn.textContent = orig;
        btn.disabled = false;
        closeTags();
      }
    };

    /* 드로어(팔로워/팔로잉) */
    let drawerMode = "followers";
    const drawer = qs("drawer_follow");
    function openDrawer(mode){ drawerMode=mode; qs("drawer_title").textContent = (mode==="followers"?"팔로워":"팔로잉"); drawer.classList.add("open"); loadDrawerPage(0); }
    function closeDrawer(){ drawer.classList.remove("open"); }
    qs("drawer_close").onclick = closeDrawer;

    async function loadDrawerPage(nextSkip){
      const st = (drawerMode==="followers")? { ...state.followers } : { ...state.following };
      st.skip = Math.max(0, nextSkip ?? st.skip);
      const q = new URLSearchParams({ skip:String(st.skip), limit:String(st.limit) });
      const base = isOtherView ? `/api/v1/users/${VIEW_USER_ID}` : "/api/v1/users/me";
      const data = await jget(`${base}/${drawerMode}?`+q.toString()).catch(()=>null);
      const tbody = qs("drawer_body"); tbody.innerHTML = "";
      (data?.items||[]).forEach(u=>{
        tbody.insertAdjacentHTML("beforeend",
          `<tr><td class="mono">${u.id??"-"}</td><td>${u.username||u.nickname||u.email||"-"}</td><td>${u.is_active===false?"inactive":"active"}</td></tr>`
        );
      });
      const total = data?.total || 0;
      const start = total? st.skip+1:0;
      const end = Math.min(st.skip+st.limit, total);
      qs("drawer_info").textContent = `${start}-${end} / ${total}`;
      qs("drawer_prev").disabled = st.skip<=0;
      qs("drawer_next").disabled = st.skip+st.limit>=total;
    }
    qs("drawer_prev").onclick = ()=> loadDrawerPage((drawerMode==="followers"?state.followers:state.following).skip - 10);
    qs("drawer_next").onclick = ()=> loadDrawerPage((drawerMode==="followers"?state.followers:state.following).skip + 10);
    qs("btn_my_followers").onclick   = ()=> openDrawer("followers");
    qs("btn_my_following").onclick   = ()=> openDrawer("following");
    if(qs('ch_prev')) qs('ch_prev').onclick = ()=> renderChallengesPage(state.challenges.page-1);
    if(qs('ch_next')) qs('ch_next').onclick = ()=> renderChallengesPage(state.challenges.page+1);

    /* 프로필 편집 모달 */
    const modalProfile = qs("modal_profile");
    function openProfile(){ modalProfile.style.display="flex"; }
    function closeProfile(){ modalProfile.style.display="none"; }

    function fillProfileForm(){
      const u = state.my || {};
      qs("edit_name").value   = u.name || "";
      qs("edit_phone").value  = u.phone || "";
      qs("edit_home").value   = u.home_region || u.region_living || "";
      qs("edit_active").value = u.active_region || u.region_active || "";
      qs("edit_intro").value  = u.introduction || "";
      qs("edit_avatar_preview").src = u.avatar_url || u.profile_image || "/static/defaults/avatar-default.png";
    }

    qs("btn_edit_profile").onclick = () => { fillProfileForm(); openProfile(); };
    qs("profile_close").onclick = closeProfile;
    qs("profile_cancel").onclick = closeProfile;

    async function uploadHandler(e){
      const f = e.target.files?.[0]; if(!f) return;
      const url = URL.createObjectURL(f);
      qs("edit_avatar_preview").src = url;
      try{
        const res = await uploadFile(f);
        const avatarUrl = res.url || res.path || res.Location || null;
        if(avatarUrl){
          try{
            const u = await jpatch("/api/v1/users/me/profile", { avatar_url: avatarUrl });
            applyProfile(u);
            toast("이미지 업로드 완료");
          }catch(e){
            applyProfile({ ...state.my, avatar_url: avatarUrl });
            toast("업로드는 되었지만 저장 API 실패");
          }
        }else{ toast("업로드 응답에 URL이 없습니다."); }
      }catch(err){ toast("업로드 실패: "+err.message); }
    }
    qs("edit_avatar_file").addEventListener("change", uploadHandler);

    qs("profile_save").onclick = async ()=>{
      const body = {
        name: qs("edit_name").value || undefined,
        phone: qs("edit_phone").value || undefined,
        home_region: qs("edit_home").value || undefined,
        active_region: qs("edit_active").value || undefined,
        introduction: qs("edit_intro").value || "",
        notify: qs("edit_notify").checked,
      };
      try{
        const u = await jpatch("/api/v1/users/me/profile", body);
        applyProfile(u);
        toast("프로필이 저장되었습니다.");
        closeProfile();
      }catch(e){
        toast("프로필 저장 API가 아직 없어요. (PATCH /api/v1/users/me/profile)");
      }
    };

    /* 태그 모달 열기/닫기 */
    const modalTags = qs("modal_tags");
    function openTags(){ modalTags.style.display="flex"; renderTagPool(); renderSelectedBar(); }
    function closeTags(){ modalTags.style.display="none"; }
    qs("btn_edit_tags2").onclick = openTags;
    qs("tags_close").onclick = closeTags;
    qs("tags_cancel").onclick = closeTags;

    /* 초기화 */
    async function init(){
      if(!token() && !GUEST){ location.href="/login"; return; }

      await loadProfile();
      await loadVisibility();

      await Promise.allSettled([
        loadSummaryAndPoints(),
        loadFollowCounts(),
        loadChallenges(),
        loadAllTags(),
        loadMyInterests(),
        loadSpendSummary(),
        loadReviews(),
      ]);

      // 보강: my_manner는 프로필 응답 기준으로 반영됨
      // init scroll reveals after content is in DOM
      initReveal();
    }


    init();
