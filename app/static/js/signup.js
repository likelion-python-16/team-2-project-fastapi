// 공통 유틸리티 함수들
function showAlert(message, type = "error") {
    const el = document.getElementById("alertContainer");
    const css = type === "error" ? "kt-alert kt-alert-danger" : "kt-alert kt-alert-success";
    el.innerHTML = `<div class="${css}">${message}</div>`;
    el.classList.remove("hidden");
}

function hideAlert() {
    const el = document.getElementById("alertContainer");
    el.innerHTML = "";
    el.classList.add("hidden");
}

// 비밀번호 보기 토글
document.getElementById("btnTogglePw")?.addEventListener("click", function() {
    const passwordInput = document.getElementById("password");
    const iconShow = document.getElementById("iconShow");
    const iconHide = document.getElementById("iconHide");
    
    if (passwordInput.type === "password") {
        passwordInput.type = "text";
        iconShow.classList.add("hidden");
        iconHide.classList.remove("hidden");
    } else {
        passwordInput.type = "password";
        iconShow.classList.remove("hidden");
        iconHide.classList.add("hidden");
    }
});

// 사용자명 중복 체크
let usernameTimeout;
document.getElementById("username")?.addEventListener("input", function() {
    clearTimeout(usernameTimeout);
    const username = this.value.trim();
    const checkEl = document.getElementById("usernameCheck");
    
    if (username.length < 3) {
        checkEl.textContent = "";
        checkEl.classList.add("hidden");
        return;
    }
    
    // 영문, 숫자만 허용 체크
    if (!/^[a-zA-Z0-9]+$/.test(username)) {
        checkEl.textContent = "영문과 숫자만 사용할 수 있습니다";
        checkEl.className = "text-xs mt-1 text-destructive";
        checkEl.classList.remove("hidden");
        return;
    }
    
    usernameTimeout = setTimeout(async () => {
        try {
            const response = await fetch(`/api/v1/auth/check-duplicates?username=${encodeURIComponent(username)}`);
            const data = await response.json();
            
            if (data.taken?.username) {
                checkEl.textContent = "이미 사용중인 사용자명입니다";
                checkEl.className = "text-xs mt-1 text-destructive";
                checkEl.classList.remove("hidden");
            } else {
                checkEl.textContent = "사용 가능한 사용자명입니다";
                checkEl.className = "text-xs mt-1 text-success";
                checkEl.classList.remove("hidden");
            }
        } catch (error) {
            console.error("Username check failed:", error);
        }
    }, 500);
});

// 이메일 중복 체크
let emailTimeout;
document.getElementById("email")?.addEventListener("input", function() {
    clearTimeout(emailTimeout);
    const email = this.value.trim();
    const checkEl = document.getElementById("emailCheck");
    
    if (!email || !email.includes("@")) {
        checkEl.textContent = "";
        checkEl.classList.add("hidden");
        return;
    }
    
    emailTimeout = setTimeout(async () => {
        try {
            const response = await fetch(`/api/v1/auth/check-duplicates?email=${encodeURIComponent(email)}`);
            const data = await response.json();
            
            if (data.taken?.email) {
                checkEl.textContent = "이미 사용중인 이메일입니다";
                checkEl.className = "text-xs mt-1 text-destructive";
                checkEl.classList.remove("hidden");
            } else {
                checkEl.textContent = "사용 가능한 이메일입니다";
                checkEl.className = "text-xs mt-1 text-success";
                checkEl.classList.remove("hidden");
            }
        } catch (error) {
            console.error("Email check failed:", error);
        }
    }, 500);
});

// 비밀번호 확인 체크
function checkPasswordMatch() {
    const password = document.getElementById("password").value;
    const confirmPassword = document.getElementById("confirmPassword").value;
    const matchEl = document.getElementById("passwordMatch");
    
    if (!confirmPassword) {
        matchEl.textContent = "";
        matchEl.classList.add("hidden");
        return;
    }
    
    if (password === confirmPassword) {
        matchEl.textContent = "비밀번호가 일치합니다";
        matchEl.className = "text-xs mt-1 text-success";
        matchEl.classList.remove("hidden");
    } else {
        matchEl.textContent = "비밀번호가 일치하지 않습니다";
        matchEl.className = "text-xs mt-1 text-destructive";
        matchEl.classList.remove("hidden");
    }
}

document.getElementById("password")?.addEventListener("input", checkPasswordMatch);
document.getElementById("confirmPassword")?.addEventListener("input", checkPasswordMatch);

// 폼 검증 함수
function validateForm() {
    const username = document.getElementById("username").value.trim();
    const name = document.getElementById("name").value.trim();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    const confirmPassword = document.getElementById("confirmPassword").value;
    const phone = document.getElementById("phone").value.trim();
    const identification = document.getElementById("identification").value.trim();
    const regionLiving = document.getElementById("regionLiving").value.trim();
    const regionActive = document.getElementById("regionActive").value.trim();
    const agreeTerms = document.getElementById("agreeTerms").checked;
    
    // 필수 필드 체크
    if (!username || !name || !email || !password || !confirmPassword || 
        !phone || !identification || !regionLiving || !regionActive) {
        showAlert("모든 필수 필드를 입력해 주세요");
        return false;
    }
    
    // 사용자명 검증
    if (username.length < 3 || username.length > 20) {
        showAlert("사용자명은 3-20자 사이여야 합니다");
        return false;
    }
    
    if (!/^[a-zA-Z0-9]+$/.test(username)) {
        showAlert("사용자명은 영문과 숫자만 사용할 수 있습니다");
        return false;
    }
    
    // 이메일 검증
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        showAlert("올바른 이메일 형식을 입력해 주세요");
        return false;
    }
    
    // 비밀번호 검증
    if (password.length < 8) {
        showAlert("비밀번호는 8자 이상이어야 합니다");
        return false;
    }
    
    if (!/(?=.*[a-zA-Z])(?=.*\d)/.test(password)) {
        showAlert("비밀번호는 영문과 숫자를 포함해야 합니다");
        return false;
    }
    
    if (password !== confirmPassword) {
        showAlert("비밀번호가 일치하지 않습니다");
        return false;
    }
    
    // 전화번호 검증
    if (!/^01[0-9]-\d{4}-\d{4}$/.test(phone)) {
        showAlert("올바른 전화번호 형식을 입력해 주세요 (010-1234-5678)");
        return false;
    }
    
    // 주민번호 검증
    if (!/^\d{6}-\d{7}$/.test(identification)) {
        showAlert("올바른 주민번호 형식을 입력해 주세요 (123456-1234567)");
        return false;
    }
    
    // 약관 동의 체크
    if (!agreeTerms) {
        showAlert("이용약관 및 개인정보처리방침에 동의해 주세요");
        return false;
    }
    
    return true;
}

// 폼 제출 이벤트
document.getElementById("signupForm")?.addEventListener("submit", async function(e) {
    e.preventDefault();
    
    if (!validateForm()) {
        return;
    }
    
    const btnSignUp = document.getElementById("btnSignUp");
    const btnText = document.getElementById("btnText");
    const btnLoading = document.getElementById("btnLoading");
    
    btnSignUp.disabled = true;
    btnText.classList.add("hidden");
    btnLoading.classList.remove("hidden");
    hideAlert();
    
    try {
        const formData = {
            username: document.getElementById("username").value.trim(),
            name: document.getElementById("name").value.trim(),
            email: document.getElementById("email").value.trim(),
            password: document.getElementById("password").value,
            phone: document.getElementById("phone").value.trim(),
            identification_number: document.getElementById("identification").value.trim(),
            region_living: document.getElementById("regionLiving").value.trim(),
            region_active: document.getElementById("regionActive").value.trim(),
            introduction: document.getElementById("introduction").value.trim() || ""
        };
        
        const response = await fetch("/api/v1/auth/signup", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(formData)
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "회원가입에 실패했습니다");
        }
        
        const data = await response.json();
        
        showAlert("회원가입이 완료되었습니다! 이메일을 확인해 주세요.", "success");
        
        setTimeout(() => {
            window.location.href = "/login";
        }, 2000);
        
    } catch (error) {
        console.error("Signup error:", error);
        showAlert(error.message || "회원가입 중 오류가 발생했습니다");
    } finally {
        btnSignUp.disabled = false;
        btnText.classList.remove("hidden");
        btnLoading.classList.add("hidden");
    }
});

// 전화번호 자동 포맷팅
document.getElementById("phone")?.addEventListener("input", function() {
    let value = this.value.replace(/[^0-9]/g, "");
    
    if (value.length >= 3) {
        if (value.length >= 7) {
            value = value.slice(0, 3) + "-" + value.slice(3, 7) + "-" + value.slice(7, 11);
        } else {
            value = value.slice(0, 3) + "-" + value.slice(3);
        }
    }
    
    this.value = value;
});

// 주민번호 자동 포맷팅
document.getElementById("identification")?.addEventListener("input", function() {
    let value = this.value.replace(/[^0-9]/g, "");
    
    if (value.length >= 6) {
        value = value.slice(0, 6) + "-" + value.slice(6, 13);
    }
    
    this.value = value;
});