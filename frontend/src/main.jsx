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
  const [workerRoutes, setWorkerRoutes] = useState([]);
  const [workers, setWorkers] = useState([]);
  const [execution, setExecution] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");

  const refreshWorkers = async () => {
    try {
      const response = await fetch(`${API_BASE}/workers`);
      if (!response.ok) throw new Error("Worker registry unavailable");
      const result = await response.json();
      setWorkers(result.workers ?? []);
    } catch {
      setWorkers([]);
    }
  };

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((response) => {
        if (!response.ok) throw new Error("Backend unavailable");
        return response.json();
      })
      .then(() => {
        setStatus("ready");
        refreshWorkers();
      })
      .catch(() => setStatus("offline"));
  }, []);

  const submit = async (event) => {
    event.preventDefault();
    const value = prompt.trim();
    if (!value || analyzing) return;

    setAnalyzing(true);
    setAnalysis(null);
    setPlan(null);
    setWorkerRoutes([]);
    setExecution(null);
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

      const routeResults = await Promise.all(
        planResult.plan.tasks.map(async (task) => {
          const response = await fetch(`${API_BASE}/route/${encodeURIComponent(task.task_type)}`);
          if (!response.ok) throw new Error(`Worker routing failed (${response.status})`);
          const result = await response.json();
          return { task, route: result };
        })
      );
      setWorkerRoutes(routeResults);

      // Stage 6B intentionally executes only the first planned task. This proves
      // the Missions UI can reach the execution layer without pretending that a
      // multi-step mission is already fully orchestrated.
      const firstTask = planResult.plan.tasks[0];
      if (firstTask) {
        const executionResponse = await fetch(`${API_BASE}/execute`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            task_type: firstTask.task_type,
            prompt: value,
          }),
        });
        if (!executionResponse.ok) {
          const detail = await executionResponse.text();
          throw new Error(`Execution request failed (${executionResponse.status}): ${detail}`);
        }
        setExecution(await executionResponse.json());
      }

      await refreshWorkers();
    } catch (requestError) {
      setError(requestError.message || "Unable to process prompt");
    } finally {
      setAnalyzing(false);
    }
  };

  const gemini = workers.find((worker) => worker.worker_id === "gemini");
  const geminiReady = Boolean(gemini?.metadata?.execution_ready);
  const geminiConfigured = Boolean(gemini?.metadata?.connector_configured);
  const geminiObserved = gemini?.resource?.observed_requests ?? 0;
  const geminiQuota = gemini?.resource?.estimated_remaining;

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
          {!analysis && <p className="intro">Describe the outcome you want. NEXUS will understand the request, decompose the work, map the best workers, connect outputs, and validate the result.</p>}

          <section className="worker-card connector-status-card">
            <div className="analysis-header">
              <div><span className="eyebrow">LIVE WORKER STATUS</span><h2>AI connector readiness</h2></div>
              <span className="plan-badge">Free-only</span>
            </div>
            <div className="worker-list">
              <div className="worker-row">
                <div className="worker-task">Gemini<small>google · {gemini?.metadata?.model ?? "connector"}</small></div>
                <div className="worker-choice">
                  <strong>{geminiReady ? "🟢 EXECUTION READY" : geminiConfigured ? "🟡 CONFIGURED · NOT TESTED" : "⚪ NOT CONFIGURED"}</strong>
                  <small>{geminiReady ? "NEXUS can route executable work here" : "Waiting for a successful connector call"}</small>
                </div>
                <div className="worker-candidates">
                  <span className="worker-chip">Observed requests · {geminiObserved}</span>
                  <span className="worker-chip">Quota · {geminiQuota == null ? "unknown" : `${geminiQuota}%`}</span>
                </div>
              </div>
            </div>
            <small className="analyzer-note">Live registry telemetry · quota is never invented when the provider does not expose it.</small>
          </section>

          <form className="composer" onSubmit={submit}>
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Tell NEXUS what you want to accomplish..." rows={4} />
            <div className="composer-footer">
              <button type="button" className="icon-button" aria-label="Attach file"><Paperclip size={18} /></button>
              <span className="hint">{analyzing ? "Understanding, planning, mapping and executing..." : "Stage 6 · Routed task execution"}</span>
              <button type="submit" className="send-button" disabled={!prompt.trim() || analyzing}><ArrowUp size={18} /></button>
            </div>
          </form>

          {error && <div className="error-card">{error}</div>}

          {execution && (
            <section className="analysis-card execution-result-card">
              <div className="analysis-header">
                <div><span className="eyebrow">NEXUS EXECUTION</span><h2>Task completed</h2></div>
                <span className="confidence">{execution.worker_name} · {execution.route_score}</span>
              </div>
              <div className="analysis-grid">
                <div><label>Worker</label><strong>{execution.worker_name}</strong></div>
                <div><label>Task type</label><strong>{execution.task_type}</strong></div>
                <div><label>Routing policy</label><strong>{execution.routing_policy}</strong></div>
                <div><label>Execution</label><strong>Completed</strong></div>
              </div>
              <div className="execution-output">{execution.output}</div>
              <small className="analyzer-note">Execution telemetry · successful requests: {execution.telemetry?.successful_requests ?? "unknown"} · latency: {execution.telemetry?.last_latency_ms ?? "unknown"} ms</small>
            </section>
          )}

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
              <small className="analyzer-note">Analyzer: {analysis.analyzer} · No external AI used</small>
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

          {workerRoutes.length > 0 && (
            <section className="worker-card">
              <div className="analysis-header">
                <div><span className="eyebrow">NEXUS WORKER MAP</span><h2>Capability-based routing</h2></div>
                <span className="plan-badge">Free-first</span>
              </div>
              <div className="worker-list">
                {workerRoutes.map(({ task, route }) => {
                  const bestProfile = route.best_profile_worker_id;
                  const recommended = route.recommended_worker_id;
                  return (
                    <div className="worker-row" key={task.task_id}>
                      <div className="worker-task">
                        {task.title}
                        <small>{route.capability} capability</small>
                      </div>
                      <div className="worker-choice">
                        <strong>{recommended ?? "No executable worker"}</strong>
                        <small>{recommended ? "current execution" : "current execution unavailable"}</small>
                        {bestProfile && bestProfile !== recommended && <small>Preferred profile: {bestProfile}</small>}
                      </div>
                      <div className="worker-candidates">
                        {route.candidates.slice(0, 3).map((candidate) => (
                          <span className="worker-chip" key={candidate.worker_id}>
                            {candidate.name} · {Math.round(candidate.score)}
                            {candidate.execution_ready ? " · ready" : " · not connected"}
                          </span>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
              <small className="analyzer-note">Routing policy: free_first_execution_aware_v2 · quota values are unknown until live connectors/telemetry are added.</small>
            </section>
          )}
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
