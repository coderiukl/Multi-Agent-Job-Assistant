import { apiFetch } from "./client";

export async function uploadCv(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await apiFetch("/cvs/upload", {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Upload CV thất bại");
  }

  return res.json();
}

export async function getCvs(skip = 0, limit = 20) {
  const res = await apiFetch(`/cvs?skip=${skip}&limit=${limit}`);

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Không lấy được danh sách CV");
  }

  return res.json();
}

export async function getCv(cvId) {
  const res = await apiFetch(`/cvs/${cvId}`);

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Không lấy được CV");
  }

  return res.json();
}

export async function deleteCv(cvId) {
  const res = await apiFetch(`/cvs/${cvId}`, {
    method: "DELETE",
  });

  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Không xóa được CV");
  }

  return true;
}