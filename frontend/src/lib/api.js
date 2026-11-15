import { visitorId } from "./visitor.js";

const API_BASE = import.meta.env.VITE_API_URL || "";
const VISITOR = { "X-Vyskar-Visitor": visitorId() };

async function request(path, options) {
  const res = await fetch(`${API_BASE}${path}`, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body?.detail || `Server returned ${res.status}`);
  return body;
}

// With app and editKey, changes that app instead of building a new one.
// A new app's response carries its edit_key.
export async function startBuild({ prompt, provider, apiKey, app, editKey }) {
  const body = await request("/api/build", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...VISITOR },
    body: JSON.stringify({
      prompt,
      provider,
      api_key: apiKey || null,
      app: app || null,
      edit_key: editKey || null,
    }),
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

// Bought builds: whether buying is on, the packs, and this browser's balance.
export function getCredits() {
  return request("/api/credits", { headers: VISITOR });
}

export function createOrder(pack) {
  return request("/api/credits/order", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...VISITOR },
    body: JSON.stringify({ pack }),
  });
}

// Razorpay's proof of payment; the server checks it before adding builds.
export function verifyPayment(proof) {
  return request("/api/credits/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...VISITOR },
    body: JSON.stringify(proof),
  });
}
