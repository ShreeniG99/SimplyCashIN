import { Home, Inbox, Calendar, Users, Settings, Zap } from "lucide-react";
import { Avatar } from "./ui.jsx";

const NAV = [
  { id: "dashboard", label: "Dashboard", icon: Home },
  { id: "inbox", label: "Collections", icon: Inbox, count: true },
  { id: "calendar", label: "Cash Calendar", icon: Calendar },
  { id: "buyers", label: "Buyers", icon: Users },
  { id: "policy", label: "Policy & Agents", icon: Settings },
];

export default function Sidebar({ screen, overdueCount, owner, onNavigate }) {
  const active = screen === "conversation" || screen === "escalation" ? "inbox" : screen;
  return (
    <aside className="side">
      <div className="brand">
        <span className="mark"><Zap size={19} strokeWidth={2.2} fill="currentColor" /></span>
        <b>Simply<span className="in">CashIN</span></b>
      </div>
      <nav className="nav">
        {NAV.map((n) => {
          const Ico = n.icon;
          return (
            <div key={n.id} className={`navitem${active === n.id ? " active" : ""}`} onClick={() => onNavigate(n.id)}>
              <Ico className="ico" strokeWidth={1.9} />
              {n.label}
              {n.count && overdueCount ? <span className="count">{overdueCount}</span> : null}
            </div>
          );
        })}
      </nav>
      <div className="side__foot">
        <Avatar name={owner?.name || "Ramesh Iyer"} tone="grey" size="sm" />
        <div className="stack">
          <span className="nm">{owner?.name || "Ramesh Iyer"}</span>
          <span className="sb">{owner?.business || "Sri Vinayaga Motors"}</span>
        </div>
      </div>
    </aside>
  );
}
