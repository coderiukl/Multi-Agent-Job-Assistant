const API_BASE_URL = "http://127.0.0.1:8000";

function getAccessToken() {
  return localStorage.getItem("access_token");
}

function getRefreshToken() {
  return localStorage.getItem("refresh_token");
}

function setTokens({ access_token, refresh_token }) {
  if (access_token) localStorage.setItem("access_token", access_token);
  if (refresh_token) localStorage.setItem("refresh_token", refresh_token);
}

function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

async function refreshAccessToken() {
  const refresh_token = getRefreshToken();
  if (!refresh_token) {
    clearTokens();
    throw new Error("Không có refresh token");
  }

  const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ refresh_token }),
  });

  if (!res.ok) {
    clearTokens();
    throw new Error("Refresh token không hợp lệ hoặc đã hết hạn");
  }

  const data = await res.json();
  setTokens(data);
  return data.access_token;
}

export async function apiFetch(path, options = {}, retry = true) {
  const token = getAccessToken();

  const headers = {
    ...(options.headers || {}),
  };

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401 && retry) {
    try {
      const newAccessToken = await refreshAccessToken();
      const retryHeaders = {
        ...(options.headers || {}),
      };

      if (!(options.body instanceof FormData)) {
        retryHeaders["Content-Type"] =
          retryHeaders["Content-Type"] || "application/json";
      }

      retryHeaders.Authorization = `Bearer ${newAccessToken}`;

      return fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers: retryHeaders,
      });
    } catch (error) {
      clearTokens();
      throw error;
    }
  }

  return response;
}

export { API_BASE_URL, getAccessToken, getRefreshToken, setTokens, clearTokens };