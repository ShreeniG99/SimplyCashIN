import { motion } from "framer-motion";
import { ArrowLeft, AlertTriangle, ShieldCheck, Check, X, Sparkles, MessageSquare, Pencil, CheckCircle2 } from "lucide-react";
import { Button, Badge, AgentChip, Card } from "../components/ui.jsx";

function Check2({ c }) {
  return (
    <div className="check">
      <span className={`ck ${c.ok ? "ok" : "no"}`}>{c.ok ? <Check size={13} /> : <X size={13} />}</span>
      <span className="k">{c.label}</span>
      <span className="v">{c.value}</span>
    </div>
  );
}

export default function Escalation({ detail, cycle, onBack, onResolve, resolution, resolving }) {
  const amount = detail.invoice.amount;
  return (
    <div className="screen">
      <header className="top">
        <Button variant="ghost" size="sm" onClick={onBack}><ArrowLeft size={16} /> Back</Button>
        <div className="stack">
          <h1 style={{ fontSize: 17 }}>Decision needed</h1>
          <span className="sub">Orchestrator paused automation and looped you in</span>
        </div>
        <div className="spacer" />
        <AgentChip agent="orchestrator" active />
      </header>

      <div className="scroll">
        <div className="body" style={{ maxWidth: "none" }}>
          <motion.div className="esc" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
            <div className="escbanner">
              <span className="ic"><AlertTriangle size={20} /></span>
              <div>
                <h2>{detail.name} · {amount}</h2>
                <p>{cycle.escalation_reason || "The proposed plan exceeds your policy guardrails and needs your decision."}</p>
              </div>
            </div>

            <div>
              <div className="sectionhd">
                <ShieldCheck size={16} style={{ color: "var(--azure-600)" }} />
                <h2>Why it escalated</h2>
                <span className="ln" />
              </div>
              <div className="stack" style={{ gap: 8, marginTop: 12 }}>
                {cycle.checks.map((c, i) => <Check2 key={i} c={c} />)}
              </div>
            </div>

            <Card accent pad style={{ display: "flex", gap: 14 }}>
              <Sparkles size={22} style={{ color: "var(--azure-600)", flex: "none", marginTop: 2 }} />
              <div>
                <div className="rowflex" style={{ marginBottom: 6, gap: 8 }}>
                  <AgentChip agent="negotiation" /><span className="muted" style={{ fontSize: 12 }}>recommends</span>
                </div>
                <div style={{ fontSize: 15, lineHeight: 1.55, color: "var(--text-strong)" }}>
                  {cycle.recommendation}
                </div>
              </div>
            </Card>

            <div>
              <div className="sectionhd">
                <MessageSquare size={16} style={{ color: "var(--azure-600)" }} />
                <h2>Message ready to send</h2>
                <span className="ln" />
                <AgentChip agent="conversation" />
              </div>
              <Card pad style={{ marginTop: 12 }}>
                <div style={{ fontSize: 14, lineHeight: 1.6, color: "var(--text-strong)" }}>
                  “{cycle.draft || "Namaste Anand ji — let's confirm a part-payment now and a short plan for the balance."}”
                </div>
                <div className="rowflex" style={{ marginTop: 12, gap: 6 }}>
                  <Badge tone="neutral" outline>Tone: {cycle.tone || "firm"} but warm</Badge>
                  {cycle.breaching_need && <Badge tone="accent">Cash need: {cycle.breaching_need}</Badge>}
                </div>
              </Card>
            </div>

            {resolution ? (
              <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}>
                <Card pad style={{ display: "flex", alignItems: "center", gap: 12, borderColor: "var(--success)", background: "var(--success-soft)" }}>
                  <CheckCircle2 size={22} style={{ color: "var(--success-fg)" }} />
                  <div>
                    <b style={{ color: "var(--success-fg)" }}>Resolved · {resolution.resolution}</b>
                    <div className="muted" style={{ fontSize: 13 }}>The agents will learn from your choice for next time.</div>
                  </div>
                  <Button variant="secondary" size="sm" style={{ marginLeft: "auto" }} onClick={onBack}>Back to dashboard</Button>
                </Card>
              </motion.div>
            ) : (
              <>
                <div className="actions">
                  <Button full disabled={resolving} onClick={() => onResolve("approve")}>
                    <Check size={16} /> Approve &amp; send
                  </Button>
                  <Button variant="secondary" full disabled={resolving} onClick={() => onResolve("edit")}>
                    <Pencil size={15} /> Edit first
                  </Button>
                  <Button variant="danger" full disabled={resolving} onClick={() => onResolve("override")}>
                    Override
                  </Button>
                </div>
                <p className="muted" style={{ fontSize: 12, textAlign: "center" }}>
                  Nothing is sent to the buyer until you approve. The agents will learn from your choice.
                </p>
              </>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  );
}
