import { useEffect, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { WifiOff } from "lucide-react";
import Sidebar from "./components/Sidebar.jsx";
import Splash from "./screens/Splash.jsx";
import Dashboard from "./screens/Dashboard.jsx";
import Conversation from "./screens/Conversation.jsx";
import Escalation from "./screens/Escalation.jsx";
import { api } from "./lib/api.js";
import { DEMO } from "./lib/demo.js";

const OWNER = { name: "Ramesh Iyer", business: "Sri Vinayaga Motors" };

export default function App() {
  const [splash, setSplash] = useState(true);
  const [screen, setScreen] = useState("dashboard");
  const [offline, setOffline] = useState(false);
  const [data, setData] = useState(null);            // {buyers, cash}
  const [detail, setDetail] = useState(null);
  const [cycle, setCycle] = useState(null);
  const [resolution, setResolution] = useState(null);
  const [resolving, setResolving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [buyers, cash] = await Promise.all([api.buyers(), api.cashCalendar()]);
        setData({ buyers, cash });
      } catch {
        setOffline(true);
        setData({ buyers: DEMO.buyers, cash: DEMO.cashCalendar });
      }
    })();
    const t = setTimeout(() => setSplash(false), 1700);
    return () => clearTimeout(t);
  }, []);

  async function openBuyer(id) {
    setScreen("conversation");
    setDetail(null); setCycle(null); setResolution(null);
    try {
      const [d, c] = await Promise.all([api.buyer(id), api.runCycle(id)]);
      setDetail(d); setCycle(c);
    } catch {
      setOffline(true);
      setDetail(DEMO.detail[id] || DEMO.detail.anand);
      setCycle(DEMO.cycle);
    }
  }

  async function resolve(action) {
    setResolving(true);
    try {
      if (!cycle.escalation_id || cycle.escalation_id === "demo-escalation") throw new Error("demo");
      const out = await api.resolve(cycle.escalation_id, action, action === "edit" ? cycle.draft : null);
      setResolution(out);
    } catch {
      const map = { approve: "approved", edit: "edited", override: "overridden" };
      setResolution({ resolved: true, resolution: map[action] || action });
    } finally {
      setResolving(false);
    }
  }

  function home() {
    setScreen("dashboard"); setDetail(null); setCycle(null); setResolution(null);
  }

  if (!data) {
    return <AnimatePresence>{splash && <Splash onEnter={() => setSplash(false)} />}</AnimatePresence>;
  }

  const overdueCount = data.buyers.filter((b) => b.status === "overdue").length;

  return (
    <div className="app">
      <Sidebar screen={screen} overdueCount={overdueCount} owner={OWNER} onHome={home} />

      {screen === "dashboard" && (
        <Dashboard buyers={data.buyers} cash={data.cash} owner={OWNER} onSelect={openBuyer} />
      )}
      {screen === "conversation" && (
        detail
          ? <Conversation detail={detail} cycle={cycle} onBack={home}
              onOpenEscalation={() => setScreen("escalation")} />
          : <Loading />
      )}
      {screen === "escalation" && detail && cycle && (
        <Escalation detail={detail} cycle={cycle} onBack={home}
          onResolve={resolve} resolution={resolution} resolving={resolving} />
      )}

      {offline && (
        <div style={{ position: "fixed", bottom: 16, left: "50%", transform: "translateX(-50%)", zIndex: 30 }}>
          <span className="offline"><WifiOff size={13} /> Demo data · live API unreachable</span>
        </div>
      )}

      <AnimatePresence>{splash && <Splash onEnter={() => setSplash(false)} />}</AnimatePresence>
    </div>
  );
}

function Loading() {
  return (
    <div className="screen">
      <div className="body" style={{ gap: 14 }}>
        <div className="skel" style={{ height: 28, width: 220 }} />
        <div className="skel" style={{ height: 120, width: "100%" }} />
        <div className="skel" style={{ height: 200, width: "100%" }} />
      </div>
    </div>
  );
}
