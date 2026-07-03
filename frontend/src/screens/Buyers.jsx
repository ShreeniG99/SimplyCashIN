import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  Upload, MessageSquare, Search, Filter, ChevronRight,
  Users, Clock, CheckCircle, AlertTriangle, XCircle, ArrowUpDown,
  FileText, Inbox, Trash2, RefreshCw,
} from "lucide-react";
import { Button, Badge, Avatar, Card } from "../components/ui.jsx";
import { parseINR } from "../lib/format.js";

const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.04 } } };
const rise = { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 0.61, 0.36, 1] } } };

function SectionTitle({ icon: Icon, title, subtitle, action }) {
  return (
    <div className="sectionhd">
      {Icon && <Icon size={16} style={{ color: "var(--azure-600)" }} />}
      <h2>{title}</h2>
      {subtitle && <span className="muted" style={{ fontSize: 12 }}>{subtitle}</span>}
      <span className="ln" />
      {action}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Buyer Table Row                                                    */
/* ------------------------------------------------------------------ */
function BuyerRow({ buyer, onSelect, index }) {
  const statusIcon = {
    paid: <CheckCircle size={14} style={{ color: "var(--success-fg)" }} />,
    overdue: <AlertTriangle size={14} style={{ color: "var(--danger-fg)" }} />,
    due: <Clock size={14} style={{ color: "var(--warning-fg)" }} />,
  };
  const statusTone = { paid: "success", overdue: "danger", due: "warning" };
  const statusLabel = { paid: "Paid", overdue: `Overdue ${buyer.overdue}d`, due: `Due · ${buyer.overdue}d` };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.3 }}
      className="buyer-row"
      onClick={() => onSelect(buyer.id)}
    >
      <div className="buyer-cell buyer-col-name">
        <Avatar name={buyer.name} tone={buyer.status === "paid" ? "success" : "grey"} size="sm" />
        <div className="stack">
          <span className="nm">{buyer.name}</span>
          <span className="sb">{buyer.tier}</span>
        </div>
      </div>

      <div className="buyer-cell buyer-col-tier">
        <span className="muted">{buyer.tier}</span>
      </div>

      <div className="buyer-cell buyer-col-amt">
        <span className="amount">{buyer.amount}</span>
      </div>

      <div className="buyer-cell buyer-col-status">
        <Badge tone={statusTone[buyer.status]} dot>
          {statusLabel[buyer.status]}
        </Badge>
      </div>

      <div className="buyer-cell buyer-col-od">
        <span style={{ fontVariantNumeric: "tabular-nums" }}>{buyer.overdue}d</span>
      </div>

      <div className="buyer-cell buyer-col-channel">
        <span className="channel-pill">
          <MessageSquare size={12} />
          {buyer.preferred_channel || "WhatsApp"}
        </span>
      </div>

      <div className="buyer-cell buyer-col-action">
        <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); onSelect(buyer.id); }}>
          View <ChevronRight size={14} />
        </Button>
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  Upload Panel                                                       */
/* ------------------------------------------------------------------ */
function UploadPanel({ onCsvUpload, onWhatsappUpload }) {
  const [csvDrag, setCsvDrag] = useState(false);
  const [wzPaste, setWzPaste] = useState("");
  const [csvJobId, setCsvJobId] = useState(null);
  const [waJobId, setWaJobId] = useState(null);

  const handleCsv = async (files) => {
    const file = files?.[0];
    if (!file) return;
    try {
      const res = await onCsvUpload(file);
      setCsvJobId(res?.job_id || "submitted");
    } catch (e) {
      alert("CSV upload failed: " + (e.message || e));
    }
  };

  const handleWaSubmit = async () => {
    if (!wzPaste.trim()) return;
    try {
      const res = await onWhatsappUpload(wzPaste.trim());
      setWaJobId(res?.job_id || "submitted");
      setWzPaste("");
    } catch (e) {
      alert("WhatsApp upload failed: " + (e.message || e));
    }
  };

  return (
    <motion.div variants={rise}>
      <div className="sectionhd">
        <Upload size={16} style={{ color: "var(--azure-600)" }} />
        <h2>Import Buyers</h2>
        <span className="ln" />
      </div>
      <Card pad style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16,
          flexWrap: "wrap"
        }}>
          {/* CSV Upload */}
          <div
            className={`upload-zone${csvDrag ? " drag" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setCsvDrag(true); }}
            onDragLeave={() => setCsvDrag(false)}
            onDrop={(e) => { e.preventDefault(); setCsvDrag(false); handleCsv(e.dataTransfer.files); }}
          >
            <Upload size={22} style={{ color: "var(--azure-600)" }} />
            <div style={{ fontSize: 13, fontWeight: 600 }}>Drop CSV here</div>
            <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
              buyer_name, buyer_tier, relationship_years, on_time_rate, preferred_channel, invoice_number, amount_rupees, due_date, status
            </div>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => handleCsv(e.target.files)}
              style={{ position: "absolute", inset: 0, opacity: 0, cursor: "pointer" }}
            />
          </div>

          {/* WhatsApp Paste */}
          <div className="upload-zone" style={{ textAlign: "left" }}>
            <MessageSquare size={20} style={{ color: "var(--azure-600)", marginBottom: 4 }} />
            <div style={{ fontSize: 13, fontWeight: 600 }}>Paste WhatsApp Chat</div>
            <textarea
              placeholder="Paste exported chat text here..."
              value={wzPaste}
              onChange={(e) => setWzPaste(e.target.value)}
              style={{
                width: "100%", height: 70, marginTop: 8, border: "1px solid var(--border-default)",
                borderRadius: "var(--radius-sm)", padding: 8, fontFamily: "inherit", fontSize: 12, resize: "none",
              }}
            />
            <Button
              size="sm"
              full
              disabled={!wzPaste.trim()}
              onClick={handleWaSubmit}
              style={{ marginTop: 6 }}
            >
              Import Chat
            </Button>
          </div>
        </div>
        {(csvJobId || waJobId) && (
          <div className="job-toast">
            {csvJobId && <span><CheckCircle size={14} /> CSV import job: <b>{csvJobId}</b></span>}
            {waJobId && <span><CheckCircle size={14} /> WhatsApp import job: <b>{waJobId}</b></span>}
          </div>
        )}
      </Card>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  Ingestion Jobs                                                     */
/* ------------------------------------------------------------------ */
function JobsPanel({ jobs, onRefresh }) {
  if (!jobs.length) return null;

  const statusIcon = {
    done: <CheckCircle size={14} style={{ color: "var(--success-fg)" }} />,
    failed: <XCircle size={14} style={{ color: "var(--danger-fg)" }} />,
    pending: <Clock size={14} style={{ color: "var(--warning-fg)" }} />,
    processing: <RefreshCw size={14} style={{ color: "var(--azure-500)" }} />,
  };

  const sourceIcon = {
    csv: <FileText size={14} />,
    whatsapp: <MessageSquare size={14} />,
  };

  return (
    <motion.div variants={rise}>
      <div className="sectionhd">
        <Inbox size={16} style={{ color: "var(--azure-600)" }} />
        <h2>Ingestion Jobs</h2>
        <span className="ln" />
      </div>
      <Card className="rows">
        {jobs.map((job) => (
          <div key={job.id} className="row">
            <div className="who">
              {sourceIcon[job.source] || <FileText size={14} />}
              <div className="stack">
                <span className="nm">{job.source === "csv" ? "CSV Upload" : "WhatsApp Import"}</span>
                <span className="sb">
                  {job.total_rows != null
                    ? `${job.imported_rows}/${job.total_rows} rows`
                    : "Processing..."}
                </span>
              </div>
            </div>
            <div className="rowflex" style={{ gap: 8, alignItems: "center" }}>
              <Badge
                tone={
                  job.status === "done"
                    ? "success"
                    : job.status === "failed"
                    ? "danger"
                    : "warning"
                }
                dot
              >
                {statusIcon[job.status]} {job.status}
              </Badge>
              {job.error_message && (
                <span className="muted" style={{ fontSize: 11 }} title={job.error_message}>
                  Error
                </span>
              )}
            </div>
          </div>
        ))}
      </Card>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  Buyer List                                                         */
/* ------------------------------------------------------------------ */
function BuyerList({ buyers, onSelect }) {
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState(1); // 1 asc, -1 desc

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir((d) => -d);
    else { setSortKey(key); setSortDir(1); }
  };

  const sorted = useMemo(() => {
    if (!sortKey) return buyers;
    const dir = sortDir;
    return [...buyers].sort((a, b) => {
      let av = a[sortKey];
      let bv = b[sortKey];
      if (sortKey === "amount") { av = parseINR(av); bv = parseINR(bv); } // amount is string like "₹2,40,000"
      if (typeof av === "string" && typeof bv === "string") return av.localeCompare(bv) * dir;
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
      return 0;
    });
  }, [buyers, sortKey, sortDir]);

  if (!buyers.length) {
    return (
      <Card pad style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>
        <Users size={32} style={{ marginBottom: 8, opacity: 0.4 }} />
        <p>No buyers found. Import data using CSV or WhatsApp above.</p>
      </Card>
    );
  }

  return (
    <Card className="buyer-table-card" style={{ overflow: "hidden", padding: 0 }}>
      <div className="buyer-table-header">
        <div className="buyer-cell buyer-col-name" onClick={() => toggleSort("name")}>
          Buyer <ArrowUpDown size={12} className={sortKey === "name" ? "active" : ""} />
        </div>
        <div className="buyer-cell buyer-col-tier" onClick={() => toggleSort("tier")}>
          Tier <ArrowUpDown size={12} className={sortKey === "tier" ? "active" : ""} />
        </div>
        <div className="buyer-cell buyer-col-amt" onClick={() => toggleSort("amount")}>
          Amount <ArrowUpDown size={12} className={sortKey === "amount" ? "active" : ""} />
        </div>
        <div className="buyer-cell buyer-col-status" onClick={() => toggleSort("status")}>
          Status <ArrowUpDown size={12} className={sortKey === "status" ? "active" : ""} />
        </div>
        <div className="buyer-cell buyer-col-od" onClick={() => toggleSort("overdue")}>
          Overdue <ArrowUpDown size={12} className={sortKey === "overdue" ? "active" : ""} />
        </div>
        <div className="buyer-cell buyer-col-channel">
          Channel
        </div>
        <div className="buyer-cell buyer-col-action" />
      </div>
      <div className="buyer-table-body">
        {sorted.map((b, i) => (
          <BuyerRow key={b.id} buyer={b} onSelect={onSelect} index={i} />
        ))}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Stats Bar                                                          */
/* ------------------------------------------------------------------ */
function StatsBar({ buyers }) {
  const active = buyers.filter((b) => b.status !== "paid");
  const overdue = buyers.filter((b) => b.status === "overdue");
  const paid = buyers.filter((b) => b.status === "paid");
  const totalAmt = active.reduce((s, b) => s + parseINR(b.amount), 0);

  const stats = [
    { label: "Total Buyers", value: buyers.length, icon: Users, tone: "azure" },
    { label: "Active", value: active.length, icon: Clock, tone: "warning" },
    { label: "Overdue", value: overdue.length, icon: AlertTriangle, tone: "danger" },
    { label: "Paid", value: paid.length, icon: CheckCircle, tone: "success" },
  ];

  return (
    <div className="buyer-stats">
      {stats.map((s) => (
        <div key={s.label} className="buyer-stat">
          <s.icon size={18} style={{ color: `var(--${s.tone}-fg, var(--text-muted))` }} />
          <div className="stack">
            <span className="buyer-stat-val">{s.value}</span>
            <span className="buyer-stat-label">{s.label}</span>
          </div>
        </div>
      ))}
      <div className="buyer-stat" style={{ marginLeft: "auto", textAlign: "right" }}>
        <span className="buyer-stat-label">Total Receivable</span>
        <span className="amount" style={{ fontSize: 18, fontWeight: 700 }}>
          ₹{totalAmt.toLocaleString("en-IN")}
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */
export default function Buyers({
  buyers,
  ingestJobs = [],
  onCsvUpload,
  onWhatsappUpload,
  onSelect,
  onRefreshJobs,
}) {
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!search.trim()) return buyers;
    const q = search.toLowerCase();
    return buyers.filter(
      (b) =>
        b.name.toLowerCase().includes(q) ||
        b.tier.toLowerCase().includes(q) ||
        b.status.toLowerCase().includes(q) ||
        (b.preferred_channel || "").toLowerCase().includes(q)
    );
  }, [buyers, search]);

  return (
    <div className="screen">
      <header className="top">
        <div className="stack">
          <h1>Buyers</h1>
          <span className="sub">{buyers.length} records · Manage buyers, import data, view status</span>
        </div>
        <div className="spacer" />
        <div className="search-box">
          <Search size={14} style={{ color: "var(--text-muted)", flex: "none" }} />
          <input
            type="text"
            placeholder="Search buyers..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </header>

      <div className="scroll">
        <motion.div className="body" variants={stagger} initial="hidden" animate="show">

          {/* Stats */}
          <motion.div variants={rise}>{buyers.length > 0 && <StatsBar buyers={buyers} />}</motion.div>

          {/* Upload */}
          <UploadPanel onCsvUpload={onCsvUpload} onWhatsappUpload={onWhatsappUpload} />

          {/* Jobs */}
          <JobsPanel jobs={ingestJobs} onRefresh={onRefreshJobs} />

          {/* Buyer Table */}
          <motion.div variants={rise}>
            <div className="sectionhd">
              <Users size={16} style={{ color: "var(--azure-600)" }} />
              <h2>All Buyers</h2>
              <span className="ln" />
              <span className="muted" style={{ fontSize: 12 }}>
                {filtered.length} of {buyers.length} shown
              </span>
            </div>
            <BuyerList buyers={filtered} onSelect={onSelect} />
          </motion.div>

        </motion.div>
      </div>
    </div>
  );
}
