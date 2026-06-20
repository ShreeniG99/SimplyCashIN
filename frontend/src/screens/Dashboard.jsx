import { motion } from "framer-motion";
import { Bell, Wallet, AlertTriangle, TrendingUp, Calendar, Inbox, ChevronRight } from "lucide-react";
import { Button, Badge, Avatar, AgentChip, Card } from "../components/ui.jsx";
import { parseINR, compactINR, dayLabel } from "../lib/format.js";

const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.05 } } };
const rise = { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 0.61, 0.36, 1] } } };

function Kpi({ label, val, alert, children }) {
  return (
    <motion.div variants={rise}>
      <Card pad className={`kpi${alert ? " alert" : ""}`}>
        <span className="k-label">{label}</span>
        <span className="k-val amount">{val}</span>
        <span className="k-meta muted">{children}</span>
      </Card>
    </motion.div>
  );
}

function calendarDays(week) {
  const by = new Map();
  for (const e of week) {
    if (!by.has(e.date)) by.set(e.date, { date: e.date, inR: 0, outR: 0, note: "" });
    const d = by.get(e.date);
    const amt = parseINR(e.amount);
    if (e.direction === "in") d.inR += amt;
    else { d.outR += amt; d.note = e.counterparty; }
  }
  return [...by.values()].sort((a, b) => a.date.localeCompare(b.date)).map((d) => ({
    ...d, ...dayLabel(d.date), need: d.outR > d.inR,
  }));
}

export default function Dashboard({ buyers, cash, owner, onSelect }) {
  const active = buyers.filter((b) => b.status !== "paid");
  const overdue = buyers.filter((b) => b.status === "overdue");
  const receivable = active.reduce((s, b) => s + parseINR(b.amount), 0);
  const overdueAmt = overdue.reduce((s, b) => s + parseINR(b.amount), 0);
  const expected = cash.week.filter((e) => e.direction === "in").reduce((s, e) => s + parseINR(e.amount), 0);
  const days = calendarDays(cash.week);
  const attention = overdue.length;

  return (
    <div className="screen">
      <header className="top">
        <div className="stack">
          <h1>Good morning, {(owner?.name || "Ramesh Iyer").split(" ")[0]}</h1>
          <span className="sub">{active.length} buyers being followed up · {attention} need your attention</span>
        </div>
        <div className="spacer" />
        <div className="agentsbar">
          <AgentChip agent="orchestrator" active />
          <span className="lbl">Agents working</span>
        </div>
        <Button variant="secondary" size="sm"><Bell size={16} /> Activity</Button>
      </header>

      <div className="scroll">
        <motion.div className="body" variants={stagger} initial="hidden" animate="show">
          <motion.div className="kpis" variants={stagger}>
            <Kpi label="Total receivable" val={compactINR(receivable)}>
              <Wallet size={14} /> across {active.length} active invoices
            </Kpi>
            <Kpi label="Overdue" val={compactINR(overdueAmt)} alert>
              <AlertTriangle size={14} style={{ color: "var(--danger-fg)" }} />
              <span style={{ color: "var(--danger-fg)" }}>{overdue.length} buyers past due</span>
            </Kpi>
            <Kpi label="Expected this week" val={compactINR(expected)}>
              <TrendingUp size={14} style={{ color: "var(--success-fg)" }} />
              <span style={{ color: "var(--success-fg)" }}>across current plans</span>
            </Kpi>
          </motion.div>

          <motion.div variants={rise}>
            <div className="sectionhd">
              <Calendar size={16} style={{ color: "var(--azure-600)" }} />
              <h2>Cash Calendar</h2>
              <span className="ln" />
              <span className="muted" style={{ fontSize: 12 }}>This week · drives how firmly agents push</span>
            </div>
            <div className="cal">
              {days.map((d) => (
                <div key={d.date} className={`calday${d.need ? " need" : ""}`}>
                  <div className="rowflex" style={{ justifyContent: "space-between" }}>
                    <span className="d">{d.dow} {d.date}</span>
                    {d.need && <Badge tone="accent">Need cash</Badge>}
                  </div>
                  <div className="stack" style={{ gap: 5 }}>
                    {d.inR > 0 && <div className="flow"><span className="pip in" /><span style={{ color: "var(--success-fg)" }}>+{compactINR(d.inR)}</span></div>}
                    {d.outR > 0 && <div className="flow"><span className="pip out" /><span style={{ color: "var(--danger-fg)" }}>−{compactINR(d.outR)}</span></div>}
                  </div>
                  {d.note && <span className="muted" style={{ fontSize: 11, marginTop: "auto" }}>{d.note}</span>}
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div variants={rise}>
            <div className="sectionhd">
              <Inbox size={16} style={{ color: "var(--azure-600)" }} />
              <h2>Active collections</h2>
              <span className="ln" />
              <Button variant="ghost" size="sm">View all</Button>
            </div>
            <Card className="rows">
              {buyers.map((b) => (
                <div key={b.id} className="row" onClick={() => onSelect(b.id)}>
                  <div className="who">
                    <Avatar name={b.name} tone={b.status === "paid" ? "success" : "grey"} />
                    <div className="stack">
                      <span className="nm">{b.name}</span>
                      <span className="sb">{b.tier}</span>
                    </div>
                  </div>
                  <span className="amt amount">{b.amount}</span>
                  <div style={{ width: 124, flex: "none" }}>
                    {b.status === "paid" ? <Badge tone="success" dot>Paid</Badge>
                      : b.status === "overdue" ? <Badge tone="danger" dot>Overdue {b.overdue}d</Badge>
                        : <Badge tone="warning" dot>Due · {b.overdue}d</Badge>}
                  </div>
                  <div className="act">
                    <span className="txt">{b.action}</span>
                  </div>
                  {b.status === "overdue" && <Badge tone="warning" outline>Needs you</Badge>}
                  <ChevronRight className="chev" size={18} />
                </div>
              ))}
            </Card>
          </motion.div>
        </motion.div>
      </div>
    </div>
  );
}
