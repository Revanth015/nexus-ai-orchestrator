import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, ArrowUp, BrainCircuit, CirclePause, Paperclip, Settings2, Sparkles } from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

function App() {
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((response) => {
        if (!response.ok) throw new Error("Backend unavailable");
        return response.json();
      })
      .then(() => setStatus("ready"))
      .catch(() => setStatus("offline"));
  }, []);

  const submit = (event) => {
    event.preventDefault();
    if (!prompt.trim()) return;
    // Stage 1 intentionally does not execute AI work yet.
    setPrompt("");
  };

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><BrainCircuit size={19} /></div><span>NEXUS</span></div>
        <button className="new-task"><Sparkles size={16} /> New task</button>
        <div className="nav-label">Workspace</div>
        <button className="nav-item active"><Activity size={16} /> Missions</button>
        <button className="nav-item"><CirclePause size={16} /> Background</button>
        <button className="nav-item"><Settings2 size={16} /> Settings</button>
        <div className="sidebar-footer">
          <span className={`dot ${status}`} />
          <div><strong>{status === "ready" ? "System ready" : status === "offline" ? "Backend offline" : "Connecting"}</strong><small>Free-only mode</small></div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div><span className="eyebrow">PERSONAL AI WORKSPACE</span><h1>What can I help you with?</h1></div>
          <div className="top-status"><span className="dot ready" /> Free-only <span className="divider" /> Background off</div>
        </header>

        <div className="center-stage">
          <div className="welcome-icon"><BrainCircuit size={28} /></div>
          <p className="intro">Describe the outcome you want. NEXUS will eventually plan the work, choose the right workers, connect their outputs, and validate the result.</p>
          <form className="composer" onSubmit={submit}>
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Tell NEXUS what you want to accomplish..." rows={4} />
            <div className="composer-footer">
              <button type="button" className="icon-button" aria-label="Attach file"><Paperclip size={18} /></button>
              <span className="hint">Stage 1 · Interface only</span>
              <button type="submit" className="send-button" disabled={!prompt.trim()}><ArrowUp size={18} /></button>
            </div>
          </form>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
