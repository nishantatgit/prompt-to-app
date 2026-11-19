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
export async function startBuild({ prompt, provider, apiKey, app, editKey, answers }) {
  const body = await request("/api/build", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...VISITOR },
    body: JSON.stringify({
      prompt,
      provider,
      api_key: apiKey || null,
      app: app || null,
      edit_key: editKey || null,
      answers: answers || [],
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

// Bring bought builds to this browser with the payment ID from the receipt.
export function restoreBuilds(paymentId) {
  return request("/api/credits/restore", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...VISITOR },
    body: JSON.stringify({ payment_id: paymentId }),
  });
}

// Feedback, optionally about one build. Real feedback on free builds can
// earn more builds once; the reply says how many.
export function sendFeedback({ jobId, rating, message, email }) {
  return request("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...VISITOR },
    body: JSON.stringify({
      job_id: jobId || null,
      rating: rating || null,
      message: message || "",
      email: email || null,
    }),
  });
}

export function joinWaitlist(email) {
  return request("/api/waitlist", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...VISITOR },
    body: JSON.stringify({ email }),
  });
}

// One or two questions worth asking before building, often none. Never
// holds up a build: a slow or failed answer means no questions.
export async function getQuestions({ prompt, provider, apiKey }, timeoutMs = 8000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const body = await request("/api/clarify", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...VISITOR },
      body: JSON.stringify({ prompt, provider, api_key: apiKey || null }),
      signal: controller.signal,
    });
    return Array.isArray(body?.questions) ? body.questions : [];
  } catch {
    return [];
  } finally {
    clearTimeout(timer);
  }
}
