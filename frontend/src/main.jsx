import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, ArrowUp, BrainCircuit, CirclePause, Paperclip, Settings2, Sparkles } from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

function App() {
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState("checking");
  const [analysis, setAnalysis] = useState(null);
  const [plan, setPlan] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((response) => {
        if (!response.ok) throw new Error("Backend unavailable");
        return response.json();
      })
      .then(() => setStatus("ready"))
      .catch(() => setStatus("offline"));
  }, []);

  const submit = async (event) => {
    event.preventDefault();
    const value = prompt.trim();
    if (!value || analyzing) return;

    setAnalyzing(true);
    setAnalysis(null);
    setPlan(null);
    setError("");

    try {
      const [analysisResponse, planResponse] = await Promise.all([
        fetch(`${API_BASE}/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt: value }),
        }),
        fetch(`${API_BASE}/plan`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt: value }),
        }),
      ]);

      if (!analysisResponse.ok) throw new Error(`Analysis request failed (${analysisResponse.status})`);
      if (!planResponse.ok) throw new Error(`Planning request failed (${planResponse.status})`);

      const [analysisResult, planResult] = await Promise.all([
        analysisResponse.json(),
        planResponse.json(),
      ]);
      setAnalysis(analysisResult.analysis);
      setPlan(planResult.plan);
    } catch (requestError) {
      setError(requestError.message || "Unable to process prompt");
    } finally {
      setAnalyzing(false);
    }
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
          <div><span className="eyebrow">PERSONAL AI WORKSPACE</span><h1>{analysis ? "Mission plan" : "What can I help you with?"}</h1></div>
          <div className="top-status"><span className="dot ready" /> Free-only <span className="divider" /> Background off</div>
        </header>

        <div className="center-stage">
          {!analysis && <div className="welcome-icon"><BrainCircuit size={28} /></div>}
          {!analysis && <p className="intro">Describe the outcome you want. NEXUS will understand the request, decompose the work, connect task outputs, choose workers later, and validate the result.</p>}

          <form className="composer" onSubmit={submit}>
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Tell NEXUS what you want to accomplish..." rows={4} />
            <div className="composer-footer">
              <button type="button" className="icon-button" aria-label="Attach file"><Paperclip size={18} /></button>
              <span className="hint">{analyzing ? "Understanding and planning..." : "Stage 3 · Task decomposition"}</span>
              <button type="submit" className="send-button" disabled={!prompt.trim() || analyzing}><ArrowUp size={18} /></button>
            </div>
          </form>

          {error && <div className="error-card">{error}</div>}

          {analysis && (
            <section className="analysis-card">
              <div className="analysis-header">
                <div><span className="eyebrow">NEXUS INTENT</span><h2>Request analysis</h2></div>
                <span className="confidence">{Math.round(analysis.confidence)}% confidence</span>
              </div>
              <div className="analysis-grid">
                <div><label>Task types</label><div className="chips">{analysis.task_types.map((item) => <span className="chip" key={item}>{item}</span>)}</div></div>
                <div><label>Deliverables</label><div className="chips">{analysis.deliverables.length ? analysis.deliverables.map((item) => <span className="chip" key={item}>{item}</span>) : <span className="muted">None explicitly detected</span>}</div></div>
                <div><label>Requirements</label><ul>{analysis.requirements.length ? analysis.requirements.map((item) => <li key={item}>{item}</li>) : <li className="muted">No additional requirements detected</li>}</ul></div>
                <div><label>Dependencies</label><ul>{analysis.dependencies.length ? analysis.dependencies.map((item) => <li key={item}>{item}</li>) : <li className="muted">No dependencies detected</li>}</ul></div>
              </div>
              <div className="flags">
                <span className={analysis.needs_research ? "flag on" : "flag"}>Research</span>
                <span className={analysis.needs_file_analysis ? "flag on" : "flag"}>File analysis</span>
                <span className={analysis.needs_current_information ? "flag on" : "flag"}>Current information</span>
                <span className={analysis.needs_presentation ? "flag on" : "flag"}>Presentation</span>
                <span className={analysis.needs_image ? "flag on" : "flag"}>Image</span>
                <span className={analysis.needs_code ? "flag on" : "flag"}>Code</span>
                <span className={analysis.needs_quality_review ? "flag on" : "flag"}>Quality review</span>
              </div>
              <small className="analyzer-note">Analyzer: {analysis.analyzer} · No external AI used in this stage</small>
            </section>
          )}

          {plan && (
            <section className="plan-card">
              <div className="analysis-header">
                <div><span className="eyebrow">NEXUS WORKFLOW</span><h2>Execution plan</h2></div>
                <span className="plan-badge">{plan.tasks.length} tasks</span>
              </div>
              <div className="task-list">
                {plan.tasks.map((task, index) => (
                  <div className="task-row" key={task.task_id}>
                    <div className="task-number">{index + 1}</div>
                    <div className="task-main">
                      <div className="task-title">{task.title}</div>
                      <div className="task-meta">{task.task_type} · {task.status}</div>
                      {task.dependencies.length > 0 && <div className="task-deps">After: {task.dependencies.join(", ")}</div>}
                      {task.inputs.length > 0 && <div className="task-deps">Inputs: {task.inputs.join(", ")}</div>}
                    </div>
                    <div className="task-output">→ {task.outputs.join(", ")}</div>
                    {task.quality_gate && <span className="gate">QUALITY GATE</span>}
                  </div>
                ))}
              </div>
              <div className="plan-notes">
                {plan.notes.map((note) => <div key={note}>• {note}</div>)}
              </div>
              <small className="analyzer-note">Planner: {plan.planner} · No AI workers called</small>
            </section>
          )}
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
