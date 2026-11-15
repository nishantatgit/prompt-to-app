import { visitorId } from "./visitor.js";

const API_BASE = import.meta.env.VITE_API_URL || "";
const VISITOR = { "X-Vyskar-Visitor": visitorId() };

async function request(path, options) {
  const res = await fetch(`${API_BASE}${path}`, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body?.detail || `Server returned ${res.status}`);
  return body;
}

export async function startBuild({ prompt, provider, apiKey }) {
  const body = await request("/api/build", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...VISITOR },
    body: JSON.stringify({ prompt, provider, api_key: apiKey || null }),
  });
  if (!body?.job_id) throw new Error("The server did not return a job id.");
  return body;
}

export function getJob(jobId) {
  return request(`/api/jobs/${encodeURIComponent(jobId)}`);
}

export function cancelJob(jobId) {
  return request(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
}

// Whether free builds are on, and how many this browser has left.
export function getTrial() {
  return request("/api/trial", { headers: VISITOR });
}

// Whether the server turns speech into text (Sarvam).
export function getVoice() {
  return request("/api/voice");
}

// A WAV recording in, English text out.
export function transcribe(wav) {
  return request("/api/transcribe", {
    method: "POST",
    headers: { "Content-Type": "audio/wav" },
    body: wav,
  });
}
