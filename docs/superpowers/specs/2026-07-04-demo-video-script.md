# SimplyCashIN — 2-Minute Hackathon Demo Video (Script + Recording Guide)

Decisions: 2:00 screen + voiceover · real Anthropic API · hero moment = HITL escalation over WebSocket · story-driven narration · scene-by-scene recording, stitched, VO recorded after (Approach B).

## Script

VO pace target: ~145 wpm. Total VO ≈ 290 words.

### Beat 1 — Hook (0:00–0:15)
**Screen:** Title card "SimplyCashIN — your receivables, collected." Cut to dashboard showing Ramesh's buyers and overdue invoices.
**VO:**
> "Ramesh runs a textile business in Surat. Four lakh rupees of his money is sitting in unpaid invoices — and today, collecting it means him personally calling and messaging buyers, every single week. SimplyCashIN gives Ramesh an AI agent that does the chasing for him."

### Beat 2 — Meet the agent (0:15–0:35)
**Screen:** Click run-cycle for buyer **rajan** (or `curl -X POST :8123/buyers/rajan/run-cycle` pre-typed in terminal, then cut to UI). Show the Claude-drafted reminder in rajan's conversation thread.
**VO:**
> "Here's an ordinary overdue invoice. The agent reads it, checks the buyer's history, and drafts a polite, personal reminder — then sends it on WhatsApp. No template. No human effort. Done."

### Beat 3 — HERO: judgment + escalation (0:35–1:15)
**Screen:**
1. Trigger run-cycle for **anand**.
2. Agent output shows ESCALATE (policy breach) — zoom/highlight the reason.
3. Escalation card appears **live** in the Escalations screen (WebSocket — no refresh).
4. You edit the message text, click Approve.
5. Dispatch confirmation appears in the thread.
**VO:**
> "But collections is about relationships — and this is where SimplyCashIN is different. Anand's account is sensitive: pushing him breaks Ramesh's own policy. Watch what the agent does. It refuses to act alone. It escalates — and the request appears on Ramesh's screen instantly, over a live socket. Ramesh softens one line, taps approve… and the agent sends it, and remembers his edit for next time. The agent knows what it should never do without a human."

### Beat 4 — It's a loop, not a blast (1:15–1:40)
**Screen:** Fire the webhook (`Will pay Friday` for anand) → reply lands in the thread. Then drag `invoices.csv` into the ingest UI / show curl → dashboard fills with newly detected overdue buyers, ordered by urgency.
**VO:**
> "And it's a real conversation. When Anand replies 'Will pay Friday', it lands in the thread and the agent adjusts. Scaling up is one upload: drop in the whole invoice book, and every overdue buyer is detected, prioritised by urgency, and queued — automatically, every day."

### Beat 5 — Close (1:40–2:00)
**Screen:** Wide dashboard shot; end card with product name + team.
**VO:**
> "Ramesh doesn't chase payments anymore. The agent chases; Ramesh only decides. SimplyCashIN — agentic receivables for India's sixty-three million small businesses. Thanks for watching."

## Recording guide

### Phase 0 — Environment prep (once, ~20 min)
1. Docker running → `docker compose up -d` in `backend/`, wait for healthy.
2. `.env`: real `ANTHROPIC_API_KEY`, `USE_STUB_LLM=0`.
3. Seed: `.venv\Scripts\python scripts\seed_dev.py`.
4. Terminal A: `uvicorn app.api.app:app --port 8123`. Terminal B: frontend `npm run dev` with `VITE_API_BASE=http://localhost:8123`.
5. **Full dry run** of beats 2–4 once to warm caches and check API latency. Then re-seed to reset state before recording.
6. Browser: 1920×1080 window, 110–125% zoom, close all other tabs, hide bookmarks bar, Do Not Disturb ON.

### Phase 1 — Record scenes (OBS, ~45 min)
- OBS: Display/Window capture, 1080p, 30 fps, record each beat as a separate clip.
- No mic during screen capture — VO comes later.
- Re-seed between failed takes (`seed_dev.py` again) so state is identical.
- Beat 3 is the money shot: put the Escalations screen visible BEFORE triggering anand's cycle so the WebSocket pop-in is on camera.
- Pre-type every curl in the terminal beforehand; on camera you only press Enter.
- Record 5 extra seconds of padding at each clip's start/end for editing.

### Phase 2 — Edit (~40 min)
- Any editor (CapCut / Clipchamp / DaVinci free).
- Trim API wait-time to ≤2 s per response (cut, don't speed-ramp — looks cleaner).
- Add a subtle zoom on the ESCALATE reason text in beat 3.
- Title card 3 s, end card 4 s. Hit exactly ≤2:00.

### Phase 3 — Voiceover (~20 min)
- Read the script against the locked edit, phone-mic-in-quiet-room is fine.
- Record each beat's VO separately; align to picture.
- Music (optional): low-volume neutral bed, duck under VO. Skip if short on time.

### Phase 4 — Export & verify
- 1080p, H.264, ≤2:00. Watch it once on your phone speaker — if VO is clear there, it's clear everywhere.

### Retake insurance
- Keep the stub fallback in your pocket: if the API misbehaves on recording day, `USE_STUB_LLM=1` still demos the full flow (text is just plainer).
- Save your best full-flow take even if imperfect — a rough complete video beats a polished incomplete one at deadline.
