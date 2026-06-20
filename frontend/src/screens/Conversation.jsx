import { motion } from "framer-motion";
import { ArrowLeft, Phone, Sparkles, Send, Check, ShieldAlert, ArrowRight } from "lucide-react";
import { Button, Badge, Avatar, AgentChip, Card } from "../components/ui.jsx";

function Msg({ m }) {
  if (m.sender === "buyer") {
    return (
      <div className="msg in">
        <Avatar name="Anand Motors" tone="grey" size="sm" />
        <div>
          <div className="meta">Anand Motors</div>
          <div className="bubble">{m.text}</div>
        </div>
      </div>
    );
  }
  const system = m.agent === "context";
  return (
    <div className={`msg out${system ? " system" : ""}`} style={system ? { maxWidth: "88%", alignSelf: "flex-start", flexDirection: "row" } : undefined}>
      <div style={{ width: system ? "100%" : undefined }}>
        <div className="meta" style={system ? undefined : { justifyContent: "flex-end" }}>
          <AgentChip agent={m.agent || "conversation"} />
          {system ? "retrieved context" : "sent"}
        </div>
        <div className="bubble">{m.text}</div>
      </div>
    </div>
  );
}

export default function Conversation({ detail, cycle, onBack, onOpenEscalation }) {
  const inv = detail.invoice;
  const escalated = cycle && cycle.decision === "escalate";
  const ctxRows = [
    ["Invoice", inv.number],
    ["Amount", inv.amount],
    ["Overdue", `${inv.overdue} days`],
    ["Relationship", detail.tier],
    ["On-time rate", `${Math.round(detail.on_time_rate * 100)}%`],
    ["Channel", detail.preferred_channel],
  ];

  return (
    <div className="screen">
      <header className="top">
        <Button variant="ghost" size="sm" onClick={onBack}><ArrowLeft size={16} /> Back</Button>
        <Avatar name={detail.name} tone="grey" />
        <div className="stack">
          <h1 style={{ fontSize: 17 }}>{detail.name}</h1>
          <span className="sub">{inv.amount} · {inv.overdue} days overdue · {detail.tier}</span>
        </div>
        <div className="spacer" />
        {inv.status === "overdue" ? <Badge tone="danger" dot>Overdue</Badge> : <Badge tone="warning" dot>Due</Badge>}
        <Button variant="secondary" size="sm"><Phone size={15} /> Call</Button>
      </header>

      <div className="conv">
        <div className="thread">
          <div className="threadscroll">
            <span className="daydiv">Conversation handled by agents</span>
            {detail.thread.map((m, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}>
                <Msg m={m} />
              </motion.div>
            ))}

            {cycle && cycle.plan && cycle.plan.length > 0 && (
              <motion.div className="msg out" style={{ maxWidth: "92%" }} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
                <div style={{ width: "100%" }}>
                  <div className="meta" style={{ justifyContent: "flex-end" }}>
                    <AgentChip agent="negotiation" active /> drafted a plan · {escalated ? "needs your OK" : "within policy"}
                  </div>
                  <div className="bubble" style={{ width: "100%" }}>
                    <div style={{ marginBottom: 10 }}>
                      A {cycle.plan.length}-part plan for {inv.amount}. {escalated ? "It exceeds your policy — review before it goes out." : "Within your policy."}
                    </div>
                    <div className="plan">
                      {cycle.plan.map((p) => (
                        <div className="planstep" key={p.n}>
                          <span className="n">{p.n}</span>
                          <span>{p.label}</span>
                          <span className="pamt right">{p.amount}</span>
                          <span className="due">{p.due}</span>
                        </div>
                      ))}
                    </div>
                    <div className="rowflex" style={{ marginTop: 12, gap: 8 }}>
                      {escalated ? (
                        <Button size="sm" variant="secondary" onClick={onOpenEscalation}>
                          <ShieldAlert size={15} /> Review escalation <ArrowRight size={14} />
                        </Button>
                      ) : (
                        <>
                          <Button size="sm"><Check size={15} /> Approve &amp; send</Button>
                          <Button size="sm" variant="secondary">Edit plan</Button>
                        </>
                      )}
                      <span className="muted" style={{ fontSize: 12, marginLeft: "auto" }}>
                        {escalated ? "Policy breach ✗" : "Within policy ✓"}
                      </span>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {escalated && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}
                className="msg system" style={{ maxWidth: "88%", alignSelf: "center", flexDirection: "row" }}>
                <div className="bubble" style={{ background: "var(--warning-soft)", borderColor: "var(--warning)", borderStyle: "solid", color: "var(--warning-fg)" }}>
                  <b>Orchestrator paused automation</b> and looped you in — the proposed plan breaches your policy guardrails.
                </div>
              </motion.div>
            )}
          </div>

          <div className="composer">
            <div className="suggest">
              <Sparkles size={18} style={{ color: "var(--azure-600)", flex: "none" }} />
              <div className="txt">
                <b style={{ color: "var(--text-strong)" }}>Conversation agent suggests: </b>
                “{cycle?.draft || "Thank you Anand ji. To keep things smooth, can we confirm a part-payment today and split the rest? I'll share a simple plan."}”
              </div>
              <Button size="sm">Use</Button>
            </div>
            <div className="inputbar">
              <input placeholder="Type a message or let the agent reply…" />
              <Button size="sm"><Send size={15} /> Send</Button>
            </div>
          </div>
        </div>

        <div className="ctx">
          <div>
            <h3>Buyer context</h3>
            <Card pad>
              {ctxRows.map(([k, v]) => (
                <div className="kv" key={k}><span className="k">{k}</span><span className="v">{v}</span></div>
              ))}
            </Card>
          </div>
          <div>
            <h3><AgentChip agent="context" /></h3>
            <Card accent pad style={{ display: "flex", gap: 10 }}>
              <Sparkles size={18} style={{ color: "var(--azure-600)", flex: "none", marginTop: 2 }} />
              <div style={{ fontSize: 13, lineHeight: 1.55 }}>
                Best past approach: <b style={{ color: "var(--text-strong)" }}>{detail.best_approach || "Short extension + early-pay nudge"}</b>.
              </div>
            </Card>
          </div>
          <div>
            <h3>Policy guardrails</h3>
            <div className="stack" style={{ gap: 8 }}>
              <div className="check"><span className="ck ok"><Check size={13} /></span><span className="k">Max extension</span><span className="v">30 days</span></div>
              <div className="check"><span className="ck ok"><Check size={13} /></span><span className="k">Min upfront</span><span className="v">30%</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
