import { apiFetch, clearTokens, setTokens } from "./client";

export async function register(payload) {
  const res = await apiFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  }, false);

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Đăng ký thất bại");
  }

  return res.json();
}

export async function login(payload) {
  const res = await apiFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  }, false);

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Đăng nhập thất bại");
  }

  const data = await res.json();
  setTokens(data);
  return data;
}

export async function logout() {
  const refresh_token = localStorage.getItem("refresh_token");

  if (!refresh_token) {
    clearTokens();
    return;
  }

  const res = await apiFetch("/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refresh_token }),
  });

  if (!res.ok && res.status !== 204) {
    clearTokens();
    return;
  }

  clearTokens();
}

export async function getMe() {
  const res = await apiFetch("/auth/me", {
    method: "GET",
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Không lấy được thông tin user");
  }

  return res.json();
}