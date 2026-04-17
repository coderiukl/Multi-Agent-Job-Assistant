import { API_BASE_URL, apiFetch, getAccessToken } from "./client";

export async function getConversations() {
  const res = await apiFetch("/conversations");

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Không lấy được danh sách hội thoại");
  }

  return res.json();
}

export async function createConversation(title = "Cuộc trò chuyện mới") {
  const res = await apiFetch("/conversations", {
    method: "POST",
    body: JSON.stringify({ title }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Không tạo được hội thoại");
  }

  return res.json();
}

export async function getConversation(conversationId) {
  const res = await apiFetch(`/conversations/${conversationId}`);

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Không lấy được hội thoại");
  }

  return res.json();
}

export async function updateConversation(conversationId, title) {
  const res = await apiFetch(`/conversations/${conversationId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Không cập nhật được hội thoại");
  }

  return res.json();
}

export async function deleteConversation(conversationId) {
  const res = await apiFetch(`/conversations/${conversationId}`, {
    method: "DELETE",
  });

  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Không xóa được hội thoại");
  }

  return true;
}

export async function getMessages(conversationId) {
  const res = await apiFetch(`/conversations/${conversationId}/messages`);

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Không lấy được messages");
  }

  return res.json();
}

/**
 * Gọi SSE chat endpoint:
 * POST /conversations/{conversation_id}/chat
 * body = FormData(message, cv_id?, file?)
 */
export async function streamChat({
  conversationId,
  message,
  cvId,
  file,
  onToken,
  onDone,
  onError,
}) {
  const token = getAccessToken();

  const formData = new FormData();
  formData.append("message", message ?? "");

  if (cvId) {
    formData.append("cv_id", cvId);
  }

  if (file) {
    formData.append("file", file);
  }

  const response = await fetch(
    `${API_BASE_URL}/conversations/${conversationId}/chat`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    }
  );

  if (!response.ok) {
    let errorMessage = "Chat request thất bại";
    try {
      const err = await response.json();
      errorMessage = err.detail || errorMessage;
    } catch {
      // ignore
    }
    throw new Error(errorMessage);
  }

  if (!response.body) {
    throw new Error("Server không trả về stream");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");

  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      const line = part
        .split("\n")
        .find((item) => item.startsWith("data: "));

      if (!line) continue;

      const raw = line.replace("data: ", "").trim();

      try {
        const payload = JSON.parse(raw);

        if (payload.token) {
          onToken?.(payload.token);
        }

        if (payload.matched_jobs) {
          onDone?.({
            matched_jobs: payload.matched_jobs,
            response_type: payload.response_type,
            done: payload.done,
          });
        } else if (payload.done) {
          onDone?.(payload);
        }

        if (payload.error) {
          onError?.(payload.error);
        }
      } catch {
        // ignore invalid chunk
      }
    }
  }
}