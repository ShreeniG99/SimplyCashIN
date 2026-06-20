// Indian-rupee helpers (UI edge only; backend stores integer paise).
export function parseINR(s) {
  if (typeof s !== "string") return Number(s) || 0;
  return parseInt(s.replace(/[^0-9]/g, ""), 10) || 0;
}

export function formatINR(rupees) {
  const s = String(Math.round(rupees));
  if (s.length <= 3) return "₹" + s;
  const head = s.slice(0, -3), tail = s.slice(-3);
  const parts = [];
  let h = head;
  while (h.length > 2) { parts.unshift(h.slice(-2)); h = h.slice(0, -2); }
  if (h) parts.unshift(h);
  return "₹" + parts.join(",") + "," + tail;
}

// 1860000 -> "₹18.6L", 32000000 -> "₹3.2Cr"
export function compactINR(rupees) {
  if (rupees >= 1e7) return "₹" + +(rupees / 1e7).toFixed(rupees % 1e7 ? 1 : 0) + "Cr";
  if (rupees >= 1e5) return "₹" + +(rupees / 1e5).toFixed(rupees % 1e5 ? 1 : 0) + "L";
  if (rupees >= 1e3) return "₹" + Math.round(rupees / 1e3) + "k";
  return "₹" + rupees;
}

export function dayLabel(iso) {
  const d = new Date(iso + "T00:00:00");
  return { dow: d.toLocaleDateString("en-IN", { weekday: "short" }), date: d.getDate() };
}
