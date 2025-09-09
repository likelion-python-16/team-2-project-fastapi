const API_BASE = "/api/v1";
let accessToken = localStorage.getItem("access_token") || "";

export function setToken(token) {
  accessToken = token || "";
  if (token) localStorage.setItem("access_token", token);
  else localStorage.removeItem("access_token");
}

export async function api(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return null;

  let data = null;
  try { data = await res.json(); } catch (_) { data = null; }

  if (!res.ok) {
    const msg = data?.detail ? (typeof data.detail === "string" ? data.detail : data.detail.message || JSON.stringify(data.detail)) : res.statusText;
    const error = new Error(msg || "Request failed");
    error.status = res.status;
    error.response = data?.detail;
    throw error;
  }
  return data;
}
