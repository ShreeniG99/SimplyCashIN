const BASE = (import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");

async function req(path, opts = {}) {
  const r = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

export const api = {
  base: BASE,
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
};
