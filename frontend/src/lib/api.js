const BASE = (import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");

async function req(path, opts = {}) {
  // Only set JSON Content-Type if body is JSON or not provided.
  // FormData needs the browser to set the multipart boundary.
  const isBodyFormData = opts.body instanceof FormData;
  const defaultHeaders = opts.body && !isBodyFormData ? { "Content-Type": "application/json" } : {};

  let r;
  try {
    r = await fetch(BASE + path, {
      headers: defaultHeaders,
      ...opts,
    });
  } catch (networkErr) {
    throw new Error(`${path} → network error: ${networkErr.message}. Is the backend running at ${BASE || "(same origin)"}?`);
  }

  if (!r.ok) {
    let detail = "";
    try {
      const body = await r.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      try { detail = await r.text(); } catch { /* ignore */ }
    }
    throw new Error(`${path} → ${r.status}${detail ? ": " + detail : ""}`);
  }
  return r.json();
}

export const api = {
  base: BASE,

  // M1 endpoints
  buyers: () => req("/buyers"),
  buyer: (id) => req(`/buyers/${id}`),
  runCycle: (id) => req(`/buyers/${id}/run-cycle`, { method: "POST" }),
  cashCalendar: () => req("/cash-calendar"),
  toggleCash: (id) => req(`/cash-events/${id}/toggle`, { method: "POST" }),
  resolve: (id, action, text = null) =>
    req(`/escalations/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ action, text }),
    }),

  // M2: Ingestion (multipart/form-data handled by browser for FormData)
  ingestCsv: (file) => {
    const form = new FormData();
    form.append("file", file);
    return req("/ingest/csv", { method: "POST", body: form });
  },
  ingestWhatsapp: (text) => {
    const blob = new Blob([text], { type: "text/plain" });
    const form = new FormData();
    form.append("file", blob, "chat.txt");
    return req("/ingest/whatsapp", { method: "POST", body: form });
  },
  ingestJobs: () => req("/ingest/jobs"),

  // M2: Redis Queue
  queue: () => req("/queue"),
  popQueue: () => req("/queue/pop", { method: "POST" }),

  // M2: Scheduler
  scheduleStatus: () => req("/schedule/status"),
  scheduleTrigger: () => req("/schedule/trigger", { method: "POST" }),
};
