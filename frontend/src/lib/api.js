const API_BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options) {
  const res = await fetch(`${API_BASE}${path}`, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body?.detail || `Server returned ${res.status}`);
  return body;
}

export async function startBuild({ prompt, provider, apiKey }) {
  const body = await request("/api/build", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, provider, api_key: apiKey || null }),
  });
  if (!body?.job_id) throw new Error("The server did not return a job id.");
  return body;
}

export function getJob(jobId) {
  return request(`/api/jobs/${encodeURIComponent(jobId)}`);
}
