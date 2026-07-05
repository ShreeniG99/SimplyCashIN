import { useEffect, useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { WifiOff } from "lucide-react";
import Sidebar from "./components/Sidebar.jsx";
import Splash from "./screens/Splash.jsx";
import Dashboard from "./screens/Dashboard.jsx";
import Buyers from "./screens/Buyers.jsx";
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

  // M2 state
  const [ingestJobs, setIngestJobs] = useState([]);
  const [queue, setQueue] = useState({ size: 0, items: [] });
  const [AVU, setAVU] = useState({ status: "unknown", queue_size: 0 });

  // M5 state: live HITL over WebSocket
  const [socket, setSocket] = useState(null);
  const [liveEscalations, setLiveEscalations] = useState([]);
  const cycleRef = useRef(null);
  useEffect(() => { cycleRef.current = cycle; }, [cycle]);

  useEffect(() => {
    let ws;
    try {
      ws = api.escalationsSocket();
    } catch {
      return undefined; // REST fallback stays in place
    }
    ws.onopen = () => setSocket(ws);
    ws.onclose = () => setSocket(null);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "escalation") {
        setLiveEscalations((prev) => [msg, ...prev.filter((e) => e.escalation_id !== msg.escalation_id)]);
      } else if (msg.type === "resolution") {
        if (cycleRef.current?.escalation_id === msg.escalation_id) {
          setResolution({ resolved: true, resolution: msg.resolution });
          setResolving(false);
        }
      } else if (msg.type === "escalation_resolved") {
        setLiveEscalations((prev) => prev.filter((e) => e.escalation_id !== msg.escalation_id));
      }
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [buyers, cash, jobs, q, sched] = await Promise.all([
          api.buyers(),
          api.cashCalendar(),
          api.ingestJobs().catch(() => DEMO.ingestJobs),
          api.queue().catch(() => DEMO.queue),
          api.scheduleStatus().catch(() => DEMO.schedule),
        ]);
        setData({ buyers, cash });
        setIngestJobs(jobs);
        setQueue(q);
        setAVU(sched);
      } catch {
        setOffline(true);
        setData({ buyers: DEMO.buyers, cash: DEMO.cashCalendar });
        setIngestJobs(DEMO.ingestJobs);
        setQueue(DEMO.queue);
        setAVU(DEMO.schedule);
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
    const text = action === "edit" ? cycle.draft : null;
    try {
      if (!cycle.escalation_id || cycle.escalation_id === "demo-escalation") throw new Error("demo");
      if (socket && socket.readyState === WebSocket.OPEN) {
        // M5: resolve over the socket; the "resolution" push completes the flow.
        socket.send(JSON.stringify({ action, escalation_id: cycle.escalation_id, text }));
        return;
      }
      const out = await api.resolve(cycle.escalation_id, action, text);
      setResolution(out);
      setResolving(false);
    } catch {
      const map = { approve: "approved", edit: "edited", override: "overridden" };
      setResolution({ resolved: true, resolution: map[action] || action });
      setResolving(false);
    }
  }

  // M2: upload CSV
  async function handleCsvUpload(file) {
    const res = await api.ingestCsv(file);
    alert(`CSV ingestion started · Job: ${res.job_id}`);
    // Refresh jobs AND buyers list after ingestion
    const [jobs, buyers] = await Promise.all([
      api.ingestJobs().catch(() => DEMO.ingestJobs),
      api.buyers().catch(() => DEMO.buyers),
    ]);
    setIngestJobs(jobs);
    setData((d) => ({ ...d, buyers }));
    return res;
  }

 useEffect(() => { // M2: auto-refresh jobs and queue on interval
    if (offline) return;
    const id = setInterval(async () => {
      try {
        const [jobs, q, sched] = await Promise.all([
          api.ingestJobs().catch(() => null),
          api.queue().catch(() => null),
          api.scheduleStatus().catch(() => null),
        ]);
        if (jobs) setIngestJobs(jobs);
        if (q) setQueue(q);
        if (sched) setAVU(sched);
      } catch { /* ignore */ }
    }, 5000);
    return () => clearInterval(id);
  }, [offline]);

  // M2: upload WhatsApp
  async function handleWhatsappUpload(text) {
    const res = await api.ingestWhatsapp(text);
    alert(`WhatsApp ingestion started · Job: ${res.job_id}`);
    const [jobs, buyers] = await Promise.all([
      api.ingestJobs().catch(() => DEMO.ingestJobs),
      api.buyers().catch(() => DEMO.buyers),
    ]);
    setIngestJobs(jobs);
    setData((d) => ({ ...d, buyers }));
    return res;
  }

  // M2: trigger scheduler
  async function handleScheduleTrigger() {
    try {
      const res = await api.scheduleTrigger();
      alert(`Scheduler triggered · Run: ${res.run_id} · Processed: ${res.processed}`);
      const q = await api.queue().catch(() => DEMO.queue);
      setQueue(q);
    } catch (e) {
      alert("Schedule trigger failed: " + (e.message || e));
    }
  }

  // M2: pop queue
  async function handlePopQueue() {
    try {
      const res = await api.popQueue();
      alert(`Popped queue · Buyer: ${res.buyer_id} · Urgency: ${res.urgency_score}`);
      const q = await api.queue().catch(() => DEMO.queue);
      setQueue(q);
    } catch (e) {
      alert("Pop failed: " + (e.message || e));
    }
  }

  function navigate(id) {
    // Nav items without a dedicated screen land where their content lives.
    const screenFor = { calendar: "dashboard", policy: "dashboard" };
    setScreen(screenFor[id] || id);
    if (id !== "conversation" && id !== "escalation") {
      setDetail(null); setCycle(null); setResolution(null);
    }
  }

  if (!data) {
    return <AnimatePresence>{splash && <Splash onEnter={() => setSplash(false)} />}</AnimatePresence>;
  }

  const overdueCount = data.buyers.filter((b) => b.status === "overdue").length;

  return (
    <div className="app">
      <Sidebar screen={screen} overdueCount={overdueCount} owner={OWNER} onNavigate={navigate} />

      {screen === "dashboard" && (
        <Dashboard
          buyers={data.buyers}
          cash={data.cash}
          owner={OWNER}
          onSelect={openBuyer}
          ingestJobs={ingestJobs}
          queue={queue}
          schedule={AVU}
          onCsvUpload={handleCsvUpload}
          onWhatsappUpload={handleWhatsappUpload}
          onScheduleTrigger={handleScheduleTrigger}
          onPopQueue={handlePopQueue}
        />
      )}
      {(screen === "buyers" || screen === "inbox") && (
        <Buyers
          buyers={data.buyers}
          ingestJobs={ingestJobs}
          onCsvUpload={handleCsvUpload}
          onWhatsappUpload={handleWhatsappUpload}
          onSelect={openBuyer}
        />
      )}
      {screen === "conversation" && (
        detail
          ? <Conversation detail={detail} cycle={cycle} onBack={() => navigate("dashboard")}
              onOpenEscalation={() => setScreen("escalation")} />
          : <Loading />
      )}
      {screen === "escalation" && detail && cycle && (
        <Escalation detail={detail} cycle={cycle} onBack={() => navigate("dashboard")}
          onResolve={resolve} resolution={resolution} resolving={resolving} />
      )}

      {offline && (
        <div style={{ position: "fixed", bottom: 16, left: "50%", transform: "translateX(-50%)", zIndex: 30 }}>
          <span className="offline"><WifiOff size={13} /> Demo data · live API unreachable</span>
        </div>
      )}

      {liveEscalations.length > 0 && screen !== "escalation" && (
        <div style={{ position: "fixed", bottom: 16, right: 16, zIndex: 30 }}>
          <span className="offline" style={{ background: "var(--azure-600)", color: "#fff" }}>
            ⚡ Live escalation · {liveEscalations[0].buyer_name} · {liveEscalations[0].amount}
            {liveEscalations.length > 1 ? ` (+${liveEscalations.length - 1} more)` : ""}
          </span>
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
