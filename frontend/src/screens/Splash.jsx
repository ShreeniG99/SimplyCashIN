import { motion } from "framer-motion";
import { Zap } from "lucide-react";

export default function Splash({ onEnter }) {
  return (
    <motion.div className="splash" initial={{ opacity: 1 }} exit={{ opacity: 0 }}
      onClick={onEnter}>
      <motion.div className="logo" initial={{ scale: 0.8, opacity: 0, rotate: -8 }}
        animate={{ scale: 1, opacity: 1, rotate: 0 }} transition={{ duration: 0.6, ease: [0.34, 1.56, 0.64, 1] }}>
        <Zap size={52} strokeWidth={2.2} fill="currentColor" />
      </motion.div>
      <motion.div className="wm" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        Simply<span className="in">CashIN</span>
      </motion.div>
      <motion.div className="tag" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}>
        Receivables that collect themselves — context, conversation and negotiation agents
        chase every overdue rupee, and loop you in only when it matters.
      </motion.div>
      <div className="dots"><i /><i /><i /></div>
    </motion.div>
  );
}
