import { api, setToken } from "./api.js";

function showAlert(message, type = "error") {
  const el = document.getElementById("alertContainer");
  const css = type === "error" ? "kt-alert-danger" : "kt-alert-success";
  el.innerHTML = `
    <div class="kt-alert ${css} p-3 rounded-lg flex items-center gap-2">
      <i class="ki-filled ${type === "error" ? "ki-information-2" : "ki-check"}"></i>
      <span class="text-sm">${message}</span>
    </div>`;
  el.classList.remove("hidden");
}

function showEmailVerificationNeeded(errorData) {
  const el = document.getElementById("alertContainer");
  el.innerHTML = `
    <div class="kt-alert p-4 rounded-lg border border-amber-200 bg-amber-50">
      <div class="flex items-start gap-3">
        <i class="ki-filled ki-information-2 text-amber-600 mt-0.5"></i>
        <div class="flex-1 min-w-0">
          <div class="text-sm font-medium text-amber-900 mb-2">이메일 인증이 필요합니다</div>
          <div class="text-sm text-amber-700 mb-4">
            <strong>${errorData.email}</strong>로 발송된 인증 메일을 확인해주세요.
          </div>
          <div class="flex flex-col sm:flex-row gap-2">
            <button id="btnResendEmail" class="kt-btn kt-btn-sm kt-btn-primary flex-shrink-0" data-user-id="${errorData.user_id}" data-email="${errorData.email}">
              <i class="ki-filled ki-message-text-2 me-1"></i>인증 메일 재발송
            </button>
            <button id="btnCloseAlert" class="kt-btn kt-btn-sm kt-btn-light flex-shrink-0">닫기</button>
          </div>
        </div>
      </div>
    </div>`;
  el.classList.remove("hidden");

  // 재발송 버튼 이벤트
  document.getElementById("btnResendEmail").addEventListener("click", async (e) => {
    const btn = e.target;
    const userId = btn.getAttribute("data-user-id");
    const email = btn.getAttribute("data-email");
    
    btn.disabled = true;
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="ki-filled ki-spinner animate-spin me-1"></i>발송 중...';
    
    try {
      await api("/auth/send-email-verification", {
        method: "POST",
        auth: false,
        body: { user_id: parseInt(userId), email: email }
      });
      
      showAlert("인증 메일이 재발송되었습니다.", "success");
    } catch (err) {
      showAlert("메일 발송에 실패했습니다: " + err.message, "error");
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  });

  // 닫기 버튼 이벤트
  document.getElementById("btnCloseAlert").addEventListener("click", () => {
    el.classList.add("hidden");
  });
}

function showPasswordResetForm(token) {
  const form = document.getElementById("signinForm");
  form.innerHTML = `
    <div class="text-center mb-2.5">
      <h3 class="text-lg font-medium text-mono leading-none mb-2.5">새 비밀번호 설정</h3>
      <div class="text-sm text-muted-foreground">
        새로운 비밀번호를 입력해 주세요
      </div>
    </div>

    <div id="alertContainer" class="hidden"></div>

    <div class="flex flex-col gap-1">
      <label class="kt-form-label font-normal text-mono">새 비밀번호</label>
      <div class="kt-input">
        <input id="newPassword" type="password" placeholder="새 비밀번호" required />
        <button class="kt-btn kt-btn-sm kt-btn-ghost kt-btn-icon bg-transparent! -me-1.5" type="button" id="btnToggleNewPw" aria-label="비밀번호 보기 전환">
          <i class="ki-filled ki-eye text-muted-foreground" id="iconShowNew"></i>
          <i class="ki-filled ki-eye-slash text-muted-foreground hidden" id="iconHideNew"></i>
        </button>
      </div>
    </div>

    <div class="flex flex-col gap-1">
      <label class="kt-form-label font-normal text-mono">비밀번호 확인</label>
      <input class="kt-input" id="confirmPassword" type="password" placeholder="비밀번호 확인" required />
    </div>

    <button class="kt-btn kt-btn-primary flex justify-center" id="btnResetPassword" type="submit">
      <span id="btnResetText">비밀번호 변경</span>
      <span id="btnResetLoading" class="hidden"><i class="ki-filled ki-spinner animate-spin me-2"></i>변경 중...</span>
    </button>
  `;

  // 새 비밀번호 토글
  const btnToggleNew = document.getElementById("btnToggleNewPw");
  btnToggleNew?.addEventListener("click", () => {
    const input = document.getElementById("newPassword");
    const iconShow = document.getElementById("iconShowNew");
    const iconHide = document.getElementById("iconHideNew");
    const isPwd = input.type === "password";
    input.type = isPwd ? "text" : "password";
    iconShow.classList.toggle("hidden", !isPwd);
    iconHide.classList.toggle("hidden", isPwd);
  });

  // 비밀번호 재설정 제출
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btnReset = document.getElementById("btnResetPassword");
    const btnResetText = document.getElementById("btnResetText");
    const btnResetLoading = document.getElementById("btnResetLoading");

    const newPassword = document.getElementById("newPassword").value;
    const confirmPassword = document.getElementById("confirmPassword").value;

    if (!newPassword || !confirmPassword) {
      showAlert("모든 필드를 입력해 주세요.");
      return;
    }

    if (newPassword !== confirmPassword) {
      showAlert("비밀번호가 일치하지 않습니다.");
      return;
    }

    if (newPassword.length < 8) {
      showAlert("비밀번호는 최소 8자 이상이어야 합니다.");
      return;
    }

    btnReset.disabled = true;
    btnResetText.classList.add("hidden");
    btnResetLoading.classList.remove("hidden");

    try {
      await api("/auth/reset-password", {
        method: "POST",
        auth: false,
        body: { token, new_password: newPassword },
      });
      
      showAlert("비밀번호가 변경되었습니다! 새 비밀번호로 로그인해 주세요.", "success");
      
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    } catch (err) {
      showAlert("비밀번호 변경 실패: " + err.message, "error");
    } finally {
      btnReset.disabled = false;
      btnResetText.classList.remove("hidden");
      btnResetLoading.classList.add("hidden");
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  // 소셜 로그인 토큰 처리 (URL 쿼리 파라미터에서)
  const urlParams = new URLSearchParams(window.location.search);
  const accessToken = urlParams.get('access_token');
  const refreshToken = urlParams.get('refresh_token');
  const resetToken = urlParams.get('reset_token');
  
  if (accessToken && refreshToken) {
    // 소셜 로그인 성공
    setToken(accessToken);
    localStorage.setItem("refresh_token", refreshToken);
    showAlert("로그인되었습니다!", "success");
    setTimeout(() => {
      window.location.href = "/home";
    }, 1000);
    return;
  }
  
  if (resetToken) {
    // 비밀번호 재설정 토큰이 있는 경우
    showPasswordResetForm(resetToken);
    return;
  }

  // 배경 이미지 적용 (필요 시)
  const bg = document.getElementById("pageBg");
  if (bg) {
    bg.style.backgroundImage = 'url("/static/assets/final/media/images/2600x1200/bg-10.png")';
    bg.style.backgroundPosition = "center";
    bg.style.backgroundRepeat = "no-repeat";
  }

  // 비밀번호 토글
  const btn = document.getElementById("btnTogglePw");
  btn?.addEventListener("click", () => {
    const input = document.getElementById("password");
    const iconShow = document.getElementById("iconShow");
    const iconHide = document.getElementById("iconHide");
    const isPwd = input.type === "password";
    input.type = isPwd ? "text" : "password";
    iconShow.classList.toggle("hidden", !isPwd);
    iconHide.classList.toggle("hidden", isPwd);
  });

  // 제출
  const form = document.getElementById("signinForm");
  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btnSignIn = document.getElementById("btnSignIn");
    const btnText = document.getElementById("btnText");
    const btnLoading = document.getElementById("btnLoading");

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    if (!username || !password) {
      showAlert("아이디와 비밀번호를 입력해 주세요.");
      return;
    }

    btnSignIn.disabled = true;
    btnText.classList.add("hidden");
    btnLoading.classList.remove("hidden");

    try {
      const data = await api("/auth/login", {
        method: "POST",
        auth: false,
        body: { login: username, password },
      });
      setToken(data?.access_token || "");
      if (data?.refresh_token) localStorage.setItem("refresh_token", data.refresh_token);

      if (document.getElementById("rememberMe").checked) {
        localStorage.setItem("remember_login", "1");
      } else {
        localStorage.removeItem("remember_login");
      }

      window.location.href = "/home";
    } catch (err) {
      // 이메일 인증이 필요한 경우 처리
      if (err.status === 403 && err.response?.action === "email_verification_required") {
        showEmailVerificationNeeded(err.response);
        return;
      }
      showAlert("로그인 실패: " + err.message, "error");
    } finally {
      btnSignIn.disabled = false;
      btnText.classList.remove("hidden");
      btnLoading.classList.add("hidden");
    }
  });
});
