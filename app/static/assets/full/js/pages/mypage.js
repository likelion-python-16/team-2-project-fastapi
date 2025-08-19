// app/static/assets/full/js/pages/mypage.js
(() => {
    const API_BASE = "/api/v1/users";
  
    // ───────── Token helpers ─────────
    const ACCESS_KEY = "access_token";
    const REFRESH_KEY = "refresh_token";
    const getAccessToken = () => localStorage.getItem(ACCESS_KEY);
    const setAccessToken = (t) => t && localStorage.setItem(ACCESS_KEY, t);
    const getRefreshToken = () => localStorage.getItem(REFRESH_KEY);
    const setRefreshToken = (t) => t && localStorage.setItem(REFRESH_KEY, t);
  
    // ───────── fetch 유틸 ─────────
    function authHeaders(extra = {}) {
      const h = new Headers(extra || {});
      if (!h.has("Content-Type")) h.set("Content-Type", "application/json");
      const t = getAccessToken();
      if (t && !h.has("Authorization")) h.set("Authorization", `Bearer ${t}`);
      return h;
    }
  
    async function tryRefresh() {
      const rt = getRefreshToken();
      if (!rt) return false;
      const res = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: rt }),
      });
      if (!res.ok) return false;
      const data = await res.json().catch(() => null);
      if (data?.access_token) {
        setAccessToken(data.access_token);
        if (data.refresh_token) setRefreshToken(data.refresh_token);
        return true;
      }
      return false;
    }
  
    async function jfetch(url, opts = {}, _retry = true) {
      const init = { ...opts };
      if (init.body && typeof init.body !== "string") {
        init.body = JSON.stringify(init.body);
        init.headers = { ...(init.headers || {}), "Content-Type": "application/json" };
      }
      init.headers = authHeaders(init.headers || {});
      const res = await fetch(url, init);
  
      if (res.status === 401 && _retry && (await tryRefresh())) {
        return jfetch(url, opts, false);
      }
  
      if (!res.ok) {
        if (res.status === 401 && !_retry) {
          localStorage.removeItem(ACCESS_KEY);
        }
        let detail = "";
        try {
          const ct = res.headers.get("content-type") || "";
          if (ct.includes("application/json")) {
            const j = await res.json();
            detail = j?.detail || j?.message || JSON.stringify(j);
          } else {
            detail = await res.text();
          }
        } catch {}
        const err = new Error(`HTTP ${res.status} ${res.statusText}${detail ? ` - ${detail}` : ""}`);
        err.status = res.status;
        err.statusText = res.statusText;
        err.body = detail;
        throw err;
      }
  
      if (res.status === 204) return null;
      const ct = res.headers.get("content-type") || "";
      return ct.includes("application/json") ? res.json() : res.text();
    }
  
    // 여러 후보 URL을 순서대로 시도(404/422는 폴백)
    async function tryFetchJson(urls, opts = {}) {
      let lastErr;
      for (const u of urls) {
        try {
          return await jfetch(u, opts);
        } catch (e) {
          lastErr = e;
          if (e?.status === 404 || e?.status === 422) continue;
          throw e;
        }
      }
      throw lastErr || new Error("No endpoint matched");
    }
  
    // ───────── 공용 유틸 ─────────
    const qs  = (sel) => document.querySelector(sel);
    const qsa = (sel) => Array.from(document.querySelectorAll(sel));
    const nfmt = (n) => Number(n || 0).toLocaleString("ko-KR");
    const setText = (sel, v) => { const el = qs(sel); if (el) el.textContent = v; };
    const cleanPhone = (v) => (v || "").replace(/\D/g, "");
    const ymd = (d) => { try { return new Date(d).toISOString().slice(0,10); } catch { return ""; } };
  
    // ✅ 짧은 날짜 포맷: 2025.08.19 11:49
    function fmtDate(s) {
      if (!s) return "-";
      const d = new Date(s);
      if (isNaN(d)) return "-";
      const z = (n) => String(n).padStart(2, "0");
      return `${d.getFullYear()}.${z(d.getMonth()+1)}.${z(d.getDate())} ${z(d.getHours())}:${z(d.getMinutes())}`;
    }
  
    // 최신 me 캐시
    let __ME_CACHE = null;
  
    // ───────── 토큰 타입 검사 & 자가치유 ─────────
    function parseJwtTyp(token) {
      try {
        const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
        return payload?.typ || payload?.type || null;
      } catch { return null; }
    }
    async function healTokensIfNeeded() {
      const a = getAccessToken();
      const r = getRefreshToken();
      if (a && parseJwtTyp(a) === "refresh") {
        if (!r) setRefreshToken(a);
        localStorage.removeItem(ACCESS_KEY);
        await tryRefresh().catch(() => {});
      }
    }
  
    // ───────── CSS/스코프 핫픽스 ─────────
    function ensureMyPageScope() {
      if (!document.querySelector('.mypage')) {
        (document.querySelector('main') || document.body).classList.add('mypage');
      }
    }
    function injectMyPageCss() {
      if (document.getElementById('mypage-hotfix')) return;
      const css = `
        .mypage .section-stack.section-stack{ display:flex !important; gap:24px !important; }
        .mypage .kt-card.kt-card{ padding:24px !important; }
        .mypage .kt-card .kt-card-header{ margin-bottom:14px !important; }
        .mypage .table-wrap{ margin-top:12px !important; }
        .mypage .summary-card{ margin-bottom:0 !important; }
        @media (max-width:640px){
          .mypage .section-stack.section-stack{ gap:16px !important; }
          .mypage .kt-card.kt-card{ padding:16px !important; }
        }
      `;
      const style = document.createElement('style');
      style.id = 'mypage-hotfix';
      style.textContent = css;
      document.head.appendChild(style);
    }
    function scrubConflictingUtilities() {
      const stack = document.querySelector('.mypage .section-stack');
      if (stack) {
        stack.classList.forEach(c => {
          if (/^(gap-0|gap-x-0|gap-y-0|space-y-\d+|space-x-\d+|!gap-0)$/.test(c)) stack.classList.remove(c);
        });
      }
      document.querySelectorAll('.mypage .kt-card').forEach(el => {
        el.classList.forEach(c => {
          if (/^(!?p-0|!px-0|!py-0|px-0|py-0)$/.test(c)) el.classList.remove(c);
        });
      });
    }
  
    // ───────── 모달 (필요 시 생성) ─────────
    function ensureEditModal() {
      let modal = document.getElementById("edit-modal");
      if (modal) return modal;
  
      modal = document.createElement("div");
      modal.id = "edit-modal";
      modal.setAttribute("role", "dialog");
      modal.style.position = "fixed";
      modal.style.inset = "0";
      modal.style.display = "none";
      modal.style.zIndex = "2147483647";
      modal.style.alignItems = "center";
      modal.style.justifyContent = "center";
  
      modal.innerHTML = `
        <div id="edit-backdrop" style="position:absolute;inset:0;background:rgba(0,0,0,.45)"></div>
        <div style="position:relative;max-width:560px;width:92%;background:#fff;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.2);overflow:hidden">
          <div style="padding:14px 18px;border-bottom:1px solid #eee;display:flex;justify-content:space-between;align-items:center">
            <div style="font-weight:600">프로필 수정</div>
            <button id="btn-cancel-edit" class="kt-btn">닫기</button>
          </div>
          <form id="profile-form" style="padding:16px 18px">
            <div class="grid grid-cols-1 gap-3">
              <label class="flex flex-col gap-1">
                <span class="text-sm text-muted">이름</span>
                <input id="inp-name" class="kt-input" type="text" />
              </label>
              <label class="flex flex-col gap-1">
                <span class="text-sm text-muted">거주지역</span>
                <input id="inp-region" class="kt-input" type="text" />
              </label>
              <label class="flex flex-col gap-1">
                <span class="text-sm text-muted">전화번호</span>
                <input id="inp-phone" class="kt-input" type="text" placeholder="010-1234-5678" />
              </label>
              <label class="flex flex-col gap-1">
                <span class="text-sm text-muted">프로필 이미지 URL</span>
                <input id="inp-profile" class="kt-input" type="url" placeholder="https://..." />
              </label>
              <label class="flex flex-col gap-1">
                <span class="text-sm text-muted">소개</span>
                <textarea id="inp-intro" class="kt-input" rows="4"></textarea>
              </label>
            </div>
            <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:14px">
              <button type="button" id="btn-cancel-edit-2" class="kt-btn">취소</button>
              <button type="submit" class="kt-btn kt-btn-primary">저장</button>
            </div>
          </form>
        </div>
      `;
      document.body.appendChild(modal);
      return modal;
    }
    function setModalVisible(visible) {
      const modal = document.getElementById("edit-modal");
      if (!modal) return;
      if (visible) {
        modal.style.display = "flex";
        modal.classList.remove("hidden","invisible","opacity-0","pointer-events-none");
        modal.style.visibility = "visible";
        modal.style.position = "fixed";
        modal.style.inset = "0";
        modal.style.alignItems = "center";
        modal.style.justifyContent = "center";
        modal.setAttribute("aria-hidden", "false");
      } else {
        modal.style.display = "none";
        modal.classList.add("hidden");
        modal.setAttribute("aria-hidden", "true");
      }
    }
    function closeEditModal() { setModalVisible(false); }
  
    // ───────── 프로필 ─────────
    async function loadMe() {
      const me = await jfetch(`${API_BASE}/me`);
      __ME_CACHE = me;
      setText("#me-name", me.name ?? me.username ?? "-");
      setText("#me-email", me.email ?? "-");
      setText("#me-manner", nfmt(me.manner_score ?? 0));
      setText("#me-points", nfmt(me.total_points ?? 0));
      setText("#me-region-living", me.region_living ?? "-");
      setText("#me-region-active", me.region_active ?? "-");
      setText("#me-phone", me.phone_number ?? me.phone ?? "-");
      setText("#me-active", me.is_active ? "활성" : "비활성");
      if (me.profile_image) qs("#me-avatar")?.setAttribute("src", me.profile_image);
    }
  
    // ───────── 지출 요약 ─────────
    async function loadSpend() {
      const res = await tryFetchJson([`${API_BASE}/me/payments?skip=0&limit=100`]);
      const items = Array.isArray(res?.items) ? res.items : Array.isArray(res) ? res : [];
  
      const includeDeposit = !!qs("#include-deposit")?.checked;
  
      let totalPaid = 0, totalRefunded = 0;
      for (const p of items) {
        const amt = Number(p?.amount ?? p?.price ?? p?.total ?? 0) || 0;
        const type = p?.payment_type; // 'fee' | 'deposit'
        if (!includeDeposit && type === "deposit") continue;
  
        const isRefund = Boolean(p?.is_refund ?? p?.refund ?? p?.isRefund) || amt < 0 || p?.status === "refunded";
        if (isRefund) totalRefunded += Math.abs(amt);
        else totalPaid += Math.max(amt, 0);
      }
      const netSpent = totalPaid - totalRefunded;
      setText("#sum-paid", nfmt(totalPaid));
      setText("#sum-refunded", nfmt(totalRefunded));
      setText("#sum-net", nfmt(netSpent));
      return { totalPaid, totalRefunded, netSpent };
    }
  
    // ───────── 포인트 내역 ─────────
    let phSkip = 0;
    const phLimit = 10;
    async function loadPoints() {
      const url = new URL(location.origin + `${API_BASE}/me/points/history`);
      const t = qs("#ph-type")?.value;
      url.searchParams.set("skip", phSkip);
      url.searchParams.set("limit", phLimit);
      if (t) url.searchParams.set("type", t);
  
      const list = await jfetch(url.toString());
      const tbody = qs("#ph-tbody");
      if (!tbody) return;
  
      tbody.innerHTML = "";
      const items = list.items || [];
      if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-6">내역이 없습니다</td></tr>`;
      } else {
        for (const r of items) {
          const deltaNum = Number(r.delta ?? r.amount ?? 0) || 0;
          const sign = deltaNum >= 0 ? "+" : "";
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td>${fmtDate(r.created_at)}</td>
            <td>${r.type ?? "-"}</td>
            <td>${sign}${nfmt(deltaNum)}</td>
            <td>${r.memo ?? ""}</td>
          `;
          tbody.appendChild(tr);
        }
      }
  
      qs("#ph-prev") && (qs("#ph-prev").disabled = phSkip <= 0);
      qs("#ph-next") && (qs("#ph-next").disabled = phSkip + phLimit >= (list.total ?? items.length));
  
      if (typeof list.current_points === "number") setText("#me-points", nfmt(list.current_points));
    }
  
    // ───────── 태그 ─────────
    async function loadTags() {
      const tags = await jfetch(`${API_BASE}/me/tags/detail`);
      const wrap = qs("#tags-wrap");
      if (!wrap) return;
      wrap.innerHTML = "";
      (tags || []).forEach((t) => {
        const chip = document.createElement("span");
        chip.className = "inline-flex items-center gap-2 bg-gray-100 rounded-full px-3 py-1";
        chip.innerHTML = `
          <i class="ki-duotone ki-category fs-3"></i>
          <span>${t.name}</span>
          <button class="ml-1 text-red-600 hover:underline" data-tag-id="${t.id}">삭제</button>
        `;
        wrap.appendChild(chip);
      });
    }
    async function addTag() {
      const id = parseInt(qs("#tag-id-input")?.value, 10);
      if (!id) return alert("tag_id를 입력하세요.");
      await jfetch(`${API_BASE}/me/tags`, { method: "POST", body: { tag_id: id } });
      const input = qs("#tag-id-input"); if (input) input.value = "";
      await loadTags();
    }
    async function removeTag(tagId) {
      await jfetch(`${API_BASE}/me/tags/${tagId}`, { method: "DELETE" });
      await loadTags();
    }
  
    // ───────── 참여한 챌린지 ─────────
    let chSkip = 0;
    const chLimit = 10;
    let chStatus = "active";
    function getChallengeListContainer() {
      const sel = "#ch-list, #challenges-wrap, #challenge-list, [data-ch-list]";
      let el = document.querySelector(sel);
      if (el) return el;
      const pager = document.querySelector("#ch-next")?.closest("div") || document.querySelector("#ch-prev")?.closest("div");
      el = document.createElement("div");
      el.id = "ch-list";
      el.className = "flex flex-col gap-2 mt-2";
      (pager && pager.parentElement ? pager.parentElement : document.body).insertBefore(el, pager || null);
      return el;
    }
    function normalizeChallenge(item) {
      const id = item?.challenge_id ?? item?.id;
      const title = item?.title ?? item?.challenge_title ?? item?.challenge?.title ?? `챌린지 #${id}`;
      const start = item?.start_date ?? item?.start_at ?? item?.started_at ?? item?.challenge?.start_date ?? item?.challenge?.start_at ?? null;
      const end   = item?.end_date   ?? item?.end_at   ?? item?.ended_at   ?? item?.challenge?.end_date   ?? item?.challenge?.end_at   ?? null;
      const cStatus = item?.challenge_status ?? item?.status ?? item?.challenge?.status;
      let isActive = cStatus === "active";
      if (cStatus == null && (start || end)) {
        const now = new Date();
        const s = start ? new Date(start) : null;
        let e = end ? new Date(end) : null;
        if (e && /^\d{4}-\d{2}-\d{2}$/.test(String(end))) e = new Date(`${end}T23:59:59`);
        isActive = (!s || s <= now) && (!e || now <= e);
      }
      const paid = item?.paid_amount ?? item?.participation_paid ?? item?.participation?.paid_amount ?? null;
      return { id, title, isActive, start, end, paid };
    }
    function chCard(c) {
      const badge = c.isActive
        ? '<span class="px-2 py-0.5 text-xs rounded bg-green-100 text-green-700">진행중</span>'
        : '<span class="px-2 py-0.5 text-xs rounded bg-gray-100 text-gray-600">종료</span>';
      const date = c.start || c.end ? `${ymd(c.start)} ~ ${ymd(c.end)}` : "";
      const paid = c.paid != null ? `<span class="text-sm text-muted">참여금: ${nfmt(c.paid)}</span>` : "";
      return `
        <div class="border rounded-lg p-3 flex items-center justify-between">
          <div>
            <div class="font-medium">${c.title}</div>
            <div class="text-xs text-muted">${date}</div>
          </div>
          <div class="flex items-center gap-3">
            ${paid}
            ${badge}
          </div>
        </div>
      `;
    }
    async function loadChallenges() {
      const urls = [
        `${API_BASE}/me/participations?skip=${chSkip}&limit=${chLimit}`,
        `${API_BASE}/me/challenges?status=${encodeURIComponent(chStatus)}&skip=${chSkip}&limit=${chLimit}`,
      ];
      const data = await tryFetchJson(urls);
      const list = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : [];
      let normalized = list.map(normalizeChallenge);
      if (chStatus !== "all") normalized = normalized.filter((c) => c.isActive);
  
      const wrap = getChallengeListContainer();
      wrap.innerHTML = normalized.length
        ? normalized.map(chCard).join("")
        : `<div class="text-sm text-muted">참여한 챌린지가 없습니다</div>`;
  
      const total = Number.isFinite(data?.total) ? data.total : normalized.length;
      const prevBtn = qs("#ch-prev");
      const nextBtn = qs("#ch-next");
      if (prevBtn) prevBtn.disabled = chSkip <= 0;
      if (nextBtn) nextBtn.disabled = chSkip + chLimit >= total;
    }
  
    // ───────── 팔로잉/팔로워 ─────────
    let followingSkip = 0, followersSkip = 0;
    const pageLimit = 10;
    let activeOnly = true;
    let activeTab = "following";
    function userChip(u) {
      const name = u.name ?? u.username ?? `#${u.id}`;
      const email = u.email ?? "";
      const isActive = u.is_active ? "활성" : "비활성";
      return `
        <div class="flex items-center justify-between border rounded-lg px-3 py-2">
          <div class="flex items-center gap-3">
            <img class="w-9 h-9 rounded-full object-cover"
                 src="${u.profile_image ?? "/static/assets/full/media/avatars/300-1.png"}" alt="">
            <div>
              <div class="font-medium">${name}</div>
              <div class="text-xs text-muted">${email} · ${isActive}</div>
            </div>
          </div>
        </div>
      `;
    }
    async function loadFollowing() {
      const url = new URL(location.origin + `${API_BASE}/me/following`);
      url.searchParams.set("only_active", activeOnly ? "true" : "false");
      url.searchParams.set("skip", followingSkip);
      url.searchParams.set("limit", pageLimit);
      const data = await jfetch(url.toString());
      const wrap = qs("#following-wrap");
      if (!wrap) return;
      wrap.innerHTML = data.items?.length ? data.items.map(userChip).join("")
        : `<div class="text-sm text-muted">팔로잉이 없습니다</div>`;
      qs("#following-prev") && (qs("#following-prev").disabled = followingSkip <= 0);
      qs("#following-next") && (qs("#following-next").disabled = followingSkip + pageLimit >= (data.total ?? 0));
    }
    async function loadFollowers() {
      const url = new URL(location.origin + `${API_BASE}/me/followers`);
      url.searchParams.set("only_active", activeOnly ? "true" : "false");
      url.searchParams.set("skip", followersSkip);
      url.searchParams.set("limit", pageLimit);
      const data = await jfetch(url.toString());
      const wrap = qs("#followers-wrap");
      if (!wrap) return;
      wrap.innerHTML = data.items?.length ? data.items.map(userChip).join("")
        : `<div class="text-sm text-muted">팔로워가 없습니다</div>`;
      qs("#followers-prev") && (qs("#followers-prev").disabled = followersSkip <= 0);
      qs("#followers-next") && (qs("#followers-next").disabled = followersSkip + pageLimit >= (data.total ?? 0));
    }
  
    // ───────── 결제 내역 ─────────
    let paySkip = 0;
    const payLimit = 10;
    const PAY_STATUS_LABELS = { pending: "대기", paid: "완료", cancelled: "취소", refunded: "환불" };
    const PAY_TYPE_LABELS   = { fee: "수수료", deposit: "예치금" };
    async function loadPayments() {
      const tbody = qs("#pay-tbody");
      if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="text-center">로딩 중...</td></tr>`;
  
      const status = qs("#pay-status")?.value || "";
      const ptype  = qs("#pay-type")?.value || "";
      const dfrom  = qs("#pay-from")?.value || "";
      const dto    = qs("#pay-to")?.value || "";
  
      const url = new URL(location.origin + `${API_BASE}/me/payments`);
      url.searchParams.set("skip", paySkip);
      url.searchParams.set("limit", payLimit);
      if (status) url.searchParams.set("status", status);
      if (ptype)  url.searchParams.set("payment_type", ptype);
      if (dfrom)  url.searchParams.set("date_from", `${dfrom}T00:00:00`);
      if (dto)    url.searchParams.set("date_to",   `${dto}T23:59:59`);
  
      try {
        const data  = await jfetch(url.toString());
        const items = Array.isArray(data?.items) ? data.items : (Array.isArray(data) ? data : []);
        if (!tbody) return;
  
        if (!items.length) {
          tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-6">내역이 없습니다</td></tr>`;
        } else {
          tbody.innerHTML = items.map(r => `
            <tr>
              <td>${r.id ?? '-'}</td>
              <td>${PAY_TYPE_LABELS[r.payment_type] ?? r.payment_type ?? '-'}</td>
              <td class="text-right">${nfmt(r.amount)}</td>
              <td>${PAY_STATUS_LABELS[r.status] ?? r.status ?? '-'}</td>
              <td>${fmtDate(r.created_at)}</td>
            </tr>
          `).join('');
        }
  
        const total = Number.isFinite(data?.total) ? data.total : items.length;
        qs("#pay-prev") && (qs("#pay-prev").disabled = paySkip <= 0);
        qs("#pay-next") && (qs("#pay-next").disabled = paySkip + payLimit >= total);
      } catch (e) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="text-center text-red-600">에러: ${e.message}</td></tr>`;
        console.error(e);
      }
    }
  
    // ───────── 신고 내역 (placeholder) ─────────
    function initReportsPlaceholder() {
      const tbody = qs("#rep-tbody");
      if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">준비 중…</td></tr>`;
    }
  
    // ───────── 프로필 수정 열기 ─────────
    async function openEditUI() {
      try { __ME_CACHE = __ME_CACHE || await jfetch(`${API_BASE}/me`); } catch (_) {}
      ensureEditModal();
  
      const me = __ME_CACHE || {};
      const setVal = (sel, v) => { const el = qs(sel); if (el) el.value = v ?? ""; };
      setVal("#inp-name",   me.name);
      setVal("#inp-region", me.region_living);
      setVal("#inp-phone",  me.phone_number ?? me.phone);
      setVal("#inp-profile", me.profile_image);
      setVal("#inp-intro",   me.introduction);
  
      setModalVisible(true);
  
      qs("#btn-cancel-edit")?.addEventListener("click", closeEditModal, { once: true });
      qs("#btn-cancel-edit-2")?.addEventListener("click", closeEditModal, { once: true });
      qs("#edit-backdrop")?.addEventListener("click", closeEditModal, { once: true });
  
      qs("#profile-form")?.addEventListener("submit", async (e) => {
        e.preventDefault();
  
        const token = getAccessToken();
        if (!token) {
          alert("로그인이 필요합니다. 다시 로그인 후 시도해 주세요.");
          return;
        }
  
        const body = {
          name:          qs("#inp-name")?.value || undefined,
          region_living: qs("#inp-region")?.value || undefined,
          phone_number:  cleanPhone(qs("#inp-phone")?.value) || undefined,
          profile_image: qs("#inp-profile")?.value || undefined,
          introduction:  qs("#inp-intro")?.value || undefined,
        };
  
        try {
          await jfetch(`${API_BASE}/me`, { method: "PATCH", body });
          closeEditModal();
          await loadMe();
        } catch (err) {
          console.error(err);
          alert("저장 실패\n" + (err.body || err.message || "알 수 없는 오류"));
        }
      }, { once: true });
    }
  
    // ───────── 모달 show/hide ─────────
    function showEditModal() {
      openEditUI().catch(err => {
        console.error(err);
        alert("프로필 편집 열기 실패: " + err.message);
      });
    }
    function hideEditModal() { closeEditModal(); }
  
    // 전역(수동 호출/디버깅용)
    window.showEditModal = showEditModal;
    window.hideEditModal = hideEditModal;
  
    // ───────── 이벤트 바인딩 & 초기 로드 ─────────
  
    // 태그 삭제(이벤트 위임)
    document.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-tag-id]");
      if (btn) {
        const id = btn.getAttribute("data-tag-id");
        removeTag(id).catch((err) => alert(err.message));
      }
    });
  
    // 프로필 수정 버튼
    document.addEventListener('click', (e) => {
      const openBtn = e.target.closest(
        '#btn-edit-profile, [data-role="edit-profile"], [data-action="edit-profile"], button[aria-label="프로필 수정"]'
      );
      if (openBtn) {
        e.preventDefault();
        showEditModal();
        return;
      }
      const cancel = e.target.closest('#btn-cancel-edit, #btn-cancel-edit-2, #edit-backdrop');
      if (cancel) {
        e.preventDefault();
        hideEditModal();
      }
    }, { capture: true });
  
    // 포인트
    qs("#btn-ph-refresh")?.addEventListener("click", () => { phSkip = 0; loadPoints().catch(console.error); });
    qs("#ph-prev")?.addEventListener("click", () => { phSkip = Math.max(0, phSkip - phLimit); loadPoints().catch(console.error); });
    qs("#ph-next")?.addEventListener("click", () => { phSkip += phLimit; loadPoints().catch(console.error); });
    qs("#ph-type")?.addEventListener("change", () => { phSkip = 0; loadPoints().catch(console.error); });
  
    // 태그
    qs("#btn-add-tag")?.addEventListener("click", () => { addTag().catch((err) => alert(err.message)); });
  
    // 지출 요약
    qs("#include-deposit")?.addEventListener("change", () => { loadSpend().catch(console.error); });
  
    // 챌린지
    qs("#ch-status")?.addEventListener("change", (e) => { chStatus = e.target.value || "active"; chSkip = 0; loadChallenges().catch(console.error); });
    qs("#ch-prev")?.addEventListener("click", () => { chSkip = Math.max(0, chSkip - chLimit); loadChallenges().catch(console.error); });
    qs("#ch-next")?.addEventListener("click", () => { chSkip += chLimit; loadChallenges().catch(console.error); });
  
    // 팔로우 탭/토글/페이징
    qs("#tab-following")?.addEventListener("click", () => {
      qs("#tab-following")?.classList.add("border-primary");
      qs("#tab-followers")?.classList.remove("border-primary");
      qs("#following-wrap")?.classList.remove("hidden");
      qs("#following-pager")?.classList.remove("hidden");
      qs("#followers-wrap")?.classList.add("hidden");
      qs("#followers-pager")?.classList.add("hidden");
      activeTab = "following"; followingSkip = 0; loadFollowing().catch(console.error);
    });
    qs("#tab-followers")?.addEventListener("click", () => {
      qs("#tab-followers")?.classList.add("border-primary");
      qs("#tab-following")?.classList.remove("border-primary");
      qs("#followers-wrap")?.classList.remove("hidden");
      qs("#followers-pager")?.classList.remove("hidden");
      qs("#following-wrap")?.classList.add("hidden");
      qs("#following-pager")?.classList.add("hidden");
      activeTab = "followers"; followersSkip = 0; loadFollowers().catch(console.error);
    });
    qs("#follow-only-active")?.addEventListener("change", () => {
      activeOnly = qs("#follow-only-active").checked;
      followingSkip = followersSkip = 0;
      (activeTab === "following" ? loadFollowing() : loadFollowers()).catch(console.error);
    });
    qs("#following-prev")?.addEventListener("click", () => { followingSkip = Math.max(0, followingSkip - pageLimit); loadFollowing().catch(console.error); });
    qs("#following-next")?.addEventListener("click", () => { followingSkip += pageLimit; loadFollowing().catch(console.error); });
    qs("#followers-prev")?.addEventListener("click", () => { followersSkip = Math.max(0, followersSkip - pageLimit); loadFollowers().catch(console.error); });
    qs("#followers-next")?.addEventListener("click", () => { followersSkip = followersSkip + pageLimit; loadFollowers().catch(console.error); });
  
    // 결제 내역
    qs("#pay-prev")?.addEventListener("click", () => { paySkip = Math.max(0, paySkip - payLimit); loadPayments(); });
    qs("#pay-next")?.addEventListener("click", () => { paySkip += payLimit; loadPayments(); });
    ["#pay-status", "#pay-type", "#pay-from", "#pay-to"].forEach((sel) =>
      qs(sel)?.addEventListener("change", () => { paySkip = 0; loadPayments(); })
    );
    qs("#pay-search")?.addEventListener("click", () => { paySkip = 0; loadPayments(); });
  
    // ───────── 초기 로드 ─────────
    (async () => {
      try {
        ensureMyPageScope();
        injectMyPageCss();
        scrubConflictingUtilities();
  
        await healTokensIfNeeded();
        if (!getAccessToken() && getRefreshToken()) {
          await tryRefresh();
        }
  
        await loadMe();
        await loadSpend();
        await loadPoints();
        await loadTags();
        await loadChallenges();
        await loadFollowing();
        await loadPayments();
        initReportsPlaceholder();
      } catch (err) {
        console.error(err);
        alert("데이터 로드 실패: " + err.message + "\n로그인이 필요할 수 있습니다. 새로고침 후 다시 시도해 주세요.");
      }
    })();
  
    // ───────── 디버깅 전역 export ─────────
    window.__mypage = {
      healTokensIfNeeded,
      tryRefresh,
      jfetch,
      getAccessToken,
      getRefreshToken,
      showEditModal,
      hideEditModal,
      injectMyPageCss,
      ensureMyPageScope,
      scrubConflictingUtilities,
      reloadAll: async () => {
        await loadMe();
        await loadSpend();
        await loadPoints();
        await loadTags();
        await loadChallenges();
        await loadFollowing();
        await loadPayments();
        initReportsPlaceholder();
      }
    };
  })();
  