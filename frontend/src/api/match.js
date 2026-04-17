import { apiFetch } from "./client";

export async function matchCvVsJd({ cv_file_id, jd_text, top_k = 5 }) {
  const res = await apiFetch("/match/cv-vs-jd", {
    method: "POST",
    body: JSON.stringify({
      cv_file_id,
      jd_text,
      top_k,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "So khớp CV với JD thất bại");
  }

  return res.json();
}

export async function getMatchingJobs(cvFileId, topK = 20) {
  const res = await apiFetch(`/match/jobs/${cvFileId}?top_k=${topK}`);

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Không lấy được job phù hợp");
  }

  return res.json();
}