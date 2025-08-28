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

document.addEventListener("DOMContentLoaded", () => {
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
      showAlert("로그인 실패: " + err.message, "error");
    } finally {
      btnSignIn.disabled = false;
      btnText.classList.remove("hidden");
      btnLoading.classList.add("hidden");
    }
  });
});
