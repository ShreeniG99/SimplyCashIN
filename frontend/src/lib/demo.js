// Offline fallback so the deployed site always renders if the API is unreachable.
// Mirrors the live API response shapes. (Live data comes from FastAPI + Supabase.)
export const DEMO = {
  buyers: [
    { id: "anand", name: "Anand Motors", tier: "Regular · 3 yrs", amount: "₹2,40,000", overdue: 14, status: "overdue", agent: null, action: "Needs follow-up", escalated: false },
    { id: "kpauto", name: "KP Auto Spares", tier: "New · 2 mo", amount: "₹85,000", overdue: 6, status: "due", agent: null, action: "Reminder scheduled", escalated: false },
    { id: "sri", name: "Sri Lakshmi Traders", tier: "Premium · 6 yrs", amount: "₹1,10,000", overdue: 2, status: "due", agent: null, action: "Reminder scheduled", escalated: false },
    { id: "metro", name: "Metro Electricals", tier: "Regular · 4 yrs", amount: "₹3,20,000", overdue: 0, status: "paid", agent: null, action: "Paid in full", escalated: false },
    { id: "rajan", name: "Rajan & Sons", tier: "Regular · 5 yrs", amount: "₹55,000", overdue: 9, status: "overdue", agent: null, action: "Needs follow-up", escalated: false },
  ],
  cashCalendar: {
    days: [
      { date: "2026-05-18", in_dots: 1, out_dots: 1 },
      { date: "2026-05-19", in_dots: 1, out_dots: 0 },
      { date: "2026-05-20", in_dots: 1, out_dots: 0 },
      { date: "2026-05-21", in_dots: 0, out_dots: 1 },
      { date: "2026-05-22", in_dots: 1, out_dots: 0 },
    ],
    week: [
      { id: "ce1", date: "2026-05-18", direction: "in", label: "Expected from Anand", counterparty: "Anand Motors", amount: "₹40,000", done: false },
      { id: "ce2", date: "2026-05-18", direction: "out", label: "GST + supplier payment", counterparty: "GST + supplier", amount: "₹1,20,000", done: false },
      { id: "ce3", date: "2026-05-19", direction: "in", label: "Expected from KP Auto", counterparty: "KP Auto", amount: "₹90,000", done: false },
      { id: "ce4", date: "2026-05-20", direction: "in", label: "Expected from Sri Lakshmi", counterparty: "Sri Lakshmi", amount: "₹1,50,000", done: false },
      { id: "ce5", date: "2026-05-21", direction: "out", label: "Staff wages", counterparty: "Wages", amount: "₹80,000", done: false },
      { id: "ce6", date: "2026-05-22", direction: "in", label: "Expected from Rajan", counterparty: "Rajan & Sons", amount: "₹1,20,000", done: false },
    ],
  },
  detail: {
    anand: {
      id: "anand", name: "Anand Motors", tier: "Regular · 3 yrs", preferred_channel: "WhatsApp Business", on_time_rate: 0.82,
      invoice: { number: "INV-2291", amount: "₹2,40,000", amount_paise: 24000000, overdue: 14, status: "overdue" },
      thread: [
        { sender: "agent", agent: "context", text: "Retrieved buyer history: 3 yrs, usually pays in 10–12 days. Last delay settled with a short extension.", created_at: "2026-05-18T10:00:00" },
        { sender: "agent", agent: "conversation", text: "Namaste Anand ji, hope business is good. A gentle reminder that invoice #INV-2291 for ₹2,40,000 is now past due. Could you share when we can expect it?", created_at: "2026-05-18T11:00:00" },
        { sender: "buyer", agent: null, text: "Sorry Ramesh, cash is tight this month. Can I pay over a few weeks?", created_at: "2026-05-18T12:00:00" },
      ],
      best_approach: "gentle message at day 7 — paid",
    },
  },
  cycle: {
    decision: "escalate",
    draft: "Namaste Anand ji, hope business is good. I understand this month is tight — let's find a way that works for both of us. Could we confirm a part-payment now and split the balance over a few weeks?",
    tone: "firm",
    plan: [
      { n: 1, label: "Upfront on confirm", amount: "₹36,000", due: "Today" },
      { n: 2, label: "Installment 2", amount: "₹1,02,000", due: "In 21 days" },
      { n: 3, label: "Installment 3", amount: "₹1,02,000", due: "In 45 days" },
    ],
    checks: [
      { label: "Within max extension (30d)", value: "plan needs 45d", ok: false },
      { label: "Minimum upfront (30%)", value: "plan offers 15%", ok: false },
      { label: "Owner cash need this week", value: "₹1,20,000 to GST + supplier due Mon", ok: true },
      { label: "Relationship tier", value: "Regular · 3 yrs · 82% on-time", ok: true },
    ],
    escalation_reason: "Within max extension (30d): plan needs 45d; Minimum upfront (30%): plan offers 15%",
    recommendation: "Hold firm — request more upfront and a shorter extension, or escalate only the balance.",
    escalation_id: "demo-escalation",
    urgency: 0.0,
    breaching_need: "₹1,20,000 to GST + supplier due Mon",
  },
};
