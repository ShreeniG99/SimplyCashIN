import { useCallback } from "react";
import { motion } from "framer-motion";
import { Bell, Wallet, AlertTriangle, TrendingUp, Calendar, Inbox, ChevronRight, Upload, MessageSquare, Zap, Clock } from "lucide-react";
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

export default function Dashboard({
  buyers, cash, owner, onSelect,
  ingestJobs = [], queue = { size: 0, items: [] }, schedule = { status: "ready", queue_size: 0 },
  onCsvUpload, onWhatsappUpload, onScheduleTrigger, onPopQueue,
}) {
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

          {/* ---- M2: Ingestion & Data Imports ---- */}
          <IngestionPanel
            ingestJobs={ingestJobs}
            onCsvUpload={onCsvUpload}
            onWhatsappUpload={onWhatsappUpload}
          />

          {/* ---- M2: Queue & Scheduler ---- */}
          <QueueSchedulerPanel
            queue={queue}
            schedule={schedule}
            onPopQueue={onPopQueue}
            onScheduleTrigger={onScheduleTrigger}
          />
        </motion.div>
      </div>
    </div>
  );
}

// ---- M2 sub-components ----

function IngestionPanel({ ingestJobs, onCsvUpload, onWhatsappUpload }) {
  const handleCsvChange = (e) => {
    const file = e.target.files[0];
    if (file && onCsvUpload) onCsvUpload(file);
  };

  const handlePaste = (e) => {
    const text = e.target.value;
    if (text && onWhatsappUpload) {
      onWhatsappUpload(text);
      e.target.value = "";
    }
  };

  return (
    <>
      <motion.div variants={rise}>
        <div className="sectionhd">
        <Upload size={16} style={{ color: "var(--azure-600)" }}/>
          <h2>Data Import</h2>
          <span className="ln" />
          <span className="muted" style={{ fontSize: 12 }}>CSV &amp; WhatsApp</span>
        </div>
        <Card pad style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="rowflex" style={{ gap: 12 }}>
            <label className="upload-btn" style={{ cursor: "pointer", flex: 1 }}>
              <input type="file" accept=".csv" style={{ display: "none" }} onChange={handleCsvChange} />
              <div style={{ border: "1px dashed var(--border-default)", borderRadius: "var(--radius-sm)", padding: "16px 20px", textAlign: "center" }}>
                <Upload size={20} style={{ color: "var(--azure-600)", marginBottom: 6 }} />
                <div style={{ fontSize: 13, fontWeight: 600 }}>Upload CSV</div>
                <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>buyers, invoices, amounts</div>
              </div>
            </label>
            <div style={{ flex: 1 }}>
              <textarea
                placeholder="Paste WhatsApp chat export..."
                style={{ width: "100%", height: 72, border: "1px solid var(--border-default)", borderRadius: "var(--radius-sm)", padding: 10, fontFamily: "inherit", fontSize: 13, resize: "none" }}
                onBlur={handlePaste}
              />
              <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>WhatsApp chat text</div>
            </div>
          </div>
        </Card>
      </motion.div>

      {ingestJobs.length > 0 && (
        <motion.div variants={rise}>
          <div className="sectionhd">
            <Clock size={16} style={{ color: "var(--azure-600)" }} />
            <h2>Ingestion Jobs</h2>
            <span className="ln" />
          </div>
          <Card className="rows">
            {ingestJobs.map((job) => (
              <div key={job.id} className="row">
                <div className="who">
                  <Avatar name={job.source} tone={job.status === "done" ? "success" : "grey"} size="sm" />
                  <div className="stack">
                    <span className="nm">{job.source === "csv" ? "CSV Upload" : "WhatsApp Import"}</span>
                    <span className="sb">
                      {job.total_rows !== null ? `${job.imported_rows}/${job.total_rows} rows` : "Processing..."}
                    </span>
                  </div>
                </div>
                <Badge tone={job.status === "done" ? "success" : job.status === "failed" ? "danger" : "warning"} dot>
                  {job.status}
                </Badge>
              </div>
            ))}
          </Card>
        </motion.div>
      )}
    </>
  );
}

function QueueSchedulerPanel({ queue, schedule, onPopQueue, onScheduleTrigger }) {
  const statusColor = schedule.status === "ready" ? "var(--success-fg)" : "var(--warning-fg)";

  return (
    <motion.div variants={rise}>
      <div className="sectionhd">
        <Zap size={16} style={{ color: "var(--azure-600)" }} />
        <h2>Automation</h2>
        <span className="ln" />
        <span className="muted" style={{ fontSize: 12 }}>Queue &amp; scheduling</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Card pad>
          <div className="rowflex" style={{ justifyContent: "space-between", marginBottom: 10 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: "var(--text-strong)" }}>Urgency Queue</span>
            <Badge tone="accent">{queue.size} items</Badge>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {queue.items.slice(0, 3).map((item, i) => (
              <div key={i} className="queue-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0", borderBottom: i < queue.items.slice(0, 3).length - 1 ? "1px solid var(--border-subtle)" : "none" }}>
                <span style={{ fontSize: 13 }}>{item.buyer_id}</span>
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{(item.urgency_score * 100).toFixed(0)}%</span>
              </div>
            ))}
            {queue.size === 0 && <span className="muted" style={{ fontSize: 13 }}>Queue empty</span>}
          </div>
          <Button full size="sm" style={{ marginTop: 12 }} onClick={onPopQueue} disabled={queue.size === 0}>
            <Zap size={14} /> Pop &amp; trigger cycle
          </Button>
        </Card>

        <Card pad>
          <div className="rowflex" style={{ justifyContent: "space-between", marginBottom: 10 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: "var(--text-strong)" }}>Daily Scheduler</span>
            <div className="rowflex" style={{ gap: 6 }}>
              <span className="bdot" style={{ background: statusColor }} />
              <span style={{ fontSize: 12, color: statusColor, fontWeight: 600 }}>{schedule.status}</span>
            </div>
          </div>
          <div style={{ fontSize: 13, color: "var(--text-body)", lineHeight: 1.55 }}>
            Runs at 9:00 AM daily to scan overdue invoices, compute cash urgency, and queue for collection cycles.
          </div>
          <div className="rowflex" style={{ marginTop: 12, gap: 8 }}>
            <Button full size="sm" onClick={onScheduleTrigger}>
              <Clock size={14} /> Trigger now
            </Button>
          </div>
        </Card>
      </div>
    </motion.div>
  );
}
