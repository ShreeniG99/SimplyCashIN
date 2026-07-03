import { Sparkles } from "lucide-react";

export function Button({ variant = "primary", size = "md", full, className = "", children, ...rest }) {
  const cls = `btn btn-${variant}${size !== "md" ? " " + size : ""}${full ? " full" : ""}${className ? " " + className : ""}`;
  return <button className={cls} {...rest}>{children}</button>;
}

export function Badge({ tone = "neutral", dot, outline, className = "", children }) {
  return (
    <span className={`badge ${tone}${outline ? " outline" : ""}${className ? " " + className : ""}`}>
      {dot && <span className="bdot" />}
      {children}
    </span>
  );
}

export function Avatar({ name = "", tone = "grey", size }) {
  const initials = name.split(" ").filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  return <span className={`avatar ${tone}${size === "sm" ? " sm" : ""}`}>{initials}</span>;
}

const AGENT_LABEL = {
  context: "Context",
  conversation: "Conversation",
  negotiation: "Negotiation",
  orchestrator: "Orchestrator",
};

export function AgentChip({ agent, active }) {
  return (
    <span className={`chip ${agent}${active ? " active" : ""}`}>
      <span className="gem" style={{ position: "relative" }}>
        <Sparkles size={9} strokeWidth={2.4} />
      </span>
      {AGENT_LABEL[agent] || agent}
    </span>
  );
}

export function Card({ accent, pad, className = "", style, children }) {
  return (
    <div className={`card${accent ? " accent" : ""}${pad ? " pad" : ""}${className ? " " + className : ""}`} style={style}>
      {children}
    </div>
  );
}
