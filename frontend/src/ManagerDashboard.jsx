import React, { useEffect, useState } from "react";
import { Activity, BrainCircuit, CheckCircle2, CircleDot, RefreshCw, Send, Users } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

const stateClass = (state = "PLANNING") => `mission-state state-${state.toLowerCase()}`;

export default function ManagerDashboard() {
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState("checking");
  const [mission, setMission] = useState(null);
  const [execution, setExecution] = useState(null);
  const [workers, setWorkers] = useState([]);
  const [memory, setMemory] = useState([]);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);

  const load = async () => {
    try {
      const [health, workerResponse, memoryResponse] = await Promise.all([
        fetch(`${API_BASE}/health`),
        fetch(`${API_BASE}/workers`),
        fetch(`${API_BASE}/corporate-memory?limit=8`),
      ]);
      if (!health.ok) throw new Error("Backend unavailable");
      setStatus("ready");
      if (workerResponse.ok) setWorkers((await workerResponse.json()).workers ?? []);
      if (memoryResponse.ok) setMemory((await memoryResponse.json()).missions ?? []);
    } catch (e) {
      setStatus("offline");
      setError(e.message || "Unable to connect to NEXUS");
    }
  };

  useEffect(() => { load(); }, []);

  const runMission = async (event) => {
    event.preventDefault();
    const objective = prompt.trim();
    if (!objective || running) return;
    setRunning(true); setError(""); setExecution(null); setMission({ objective, state: "PLANNING", tasks: [], active_workers: [], rework_count: 0, max_reworks: 3 });
    try {
      const response = await fetch(`${API_BASE}/execute-mission`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt: objective, file_ids: [] }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || `Mission failed (${response.status})`);
      setExecution(result);
      setMission({ objective: result.objective, state: result.status === "completed" ? "COMPLETED" : "MANAGER_REVIEW", tasks: result.tasks ?? [], active_workers: [...new Set((result.tasks ?? []).map(t => t.worker_name).filter(Boolean))], rework_count: result.rework_count ?? 0, max_reworks: result.max_reworks ?? 3 });
      await load();
    } catch (e) { setError(e.message || "Mission execution failed"); }
    finally { setRunning(false); }
  };

  const completed = execution?.tasks?.filter(t => ["completed", "reviewed"].includes(t.status)).length ?? 0;
  const total = execution?.tasks?.length ?? 0;
  const workersUsed = mission?.active_workers?.length ?? 0;

  return (
    <main className="manager-shell">
      <header className="manager-header">
        <div className="manager-brand"><span className="manager-logo"><BrainCircuit size={21} /></span><div><div className="manager-title">NEXUS</div><div className="manager-subtitle">AI CORPORATE MANAGER</div></div></div>
        <div className="manager-status"><span className={`dot ${status === "ready" ? "ready" : status === "offline" ? "offline" : ""}`} /> {status === "ready" ? "Manager online" : status === "offline" ? "Backend offline" : "Connecting"}<button className="manager-refresh" onClick={load} title="Refresh"><RefreshCw size={15} /></button></div>
      </header>

      <div className="manager-grid">
        <section className="manager-main">
          <div className="manager-hero"><span className="eyebrow">CEO COMMAND CENTER</span><h1>What should NEXUS accomplish?</h1><p>The Manager decomposes your objective, allocates AI employees by task-specific evidence, coordinates collaboration, sends work through QA, records rework problems and makes the final acceptance decision.</p></div>
          <form className="manager-command" onSubmit={runMission}>
            <textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows={4} placeholder="Give NEXUS the business outcome, not the individual steps..." />
            <div className="manager-command-footer"><span>Free-first workforce · maximum 3 reworks</span><button disabled={!prompt.trim() || running}><Send size={16} /> {running ? "Manager executing..." : "Start mission"}</button></div>
          </form>
          {error && <div className="error-card">{error}</div>}

          {mission && <section className="manager-card">
            <div className="manager-card-head"><div><span className="eyebrow">ACTIVE MISSION</span><h2>{mission.objective}</h2></div><span className={stateClass(mission.state)}>{mission.state}</span></div>
            <div className="manager-metrics"><div><strong>{completed}/{total}</strong><small>Tasks completed</small></div><div><strong>{workersUsed}</strong><small>AI employees used</small></div><div><strong>{mission.rework_count}/{mission.max_reworks}</strong><small>Reworks</small></div><div><strong>{execution?.manager_decision ?? "PLANNING"}</strong><small>Manager decision</small></div></div>
            <div className="sprint-line"><span>Sprint 1</span><span>→</span><span>Plan</span><span>→</span><span>Allocate</span><span>→</span><span>Execute</span><span>→</span><span>QA</span><span>→</span><span>Manager review</span></div>
            {execution?.tasks?.length > 0 && <div className="manager-task-board">{execution.tasks.map((task, i) => <div className="manager-task" key={`${task.task_id}-${i}`}><div className="task-icon">{task.status === "completed" || task.status === "reviewed" ? <CheckCircle2 size={17} /> : <CircleDot size={17} />}</div><div className="task-copy"><strong>{task.title}</strong><small>{task.task_type} · {task.status} · Sprint {task.sprint ?? 1}</small>{task.worker_name && <small>Employee: {task.worker_name} · route score {task.route_score ?? "—"}</small>}{task.rework_problem && <small className="rework-note">Rework problem: {task.rework_problem}</small>}{task.quality_decision && <small>QA: {task.quality_decision} · Manager: {task.manager_decision ?? "pending"}</small>}</div><span className={`task-status ${task.status}`}>{task.status}</span></div>)}</div>}
          </section>}

          {execution?.artifacts?.length > 0 && <section className="manager-card"><div className="manager-card-head"><div><span className="eyebrow">DELIVERABLES</span><h2>Employee outputs</h2></div><span className="manager-count">{execution.artifacts.length}</span></div>{execution.artifacts.map(a => <details className="manager-artifact" key={a.artifact_id}><summary><strong>{a.name}</strong><span>{a.artifact_type} · {a.size_chars} chars</span></summary><pre>{a.content}</pre></details>)}</section>}
        </section>

        <aside className="manager-side">
          <section className="manager-card"><div className="manager-card-head"><div><span className="eyebrow">WORKFORCE</span><h2>AI employees</h2></div><Users size={17} /></div><div className="employee-list">{workers.map(w => <div className="employee" key={w.worker_id}><div className="employee-icon"><Activity size={15} /></div><div><strong>{w.name ?? w.worker_id}</strong><small>{w.worker_id} · {w.resource?.status ?? "registered"}</small></div><span className={w.metadata?.execution_ready ? "employee-ready" : "employee-idle"}>{w.metadata?.execution_ready ? "READY" : "OFFLINE"}</span></div>)}{workers.length === 0 && <div className="muted">No worker registry data yet.</div>}</div></section>
          <section className="manager-card"><div className="manager-card-head"><div><span className="eyebrow">CORPORATE MEMORY</span><h2>Previous missions</h2></div></div>{memory.length === 0 ? <div className="muted">No completed missions stored yet.</div> : <div className="memory-list">{memory.map(m => <div className="memory-item" key={m.mission_id}><strong>{m.objective}</strong><small>{m.task_count} tasks · {m.worker_count} employees · {m.rework_count} reworks</small><small>{m.final_decision} · quality {m.final_quality ?? "—"}</small></div>)}</div>}</section>
          <section className="manager-card manager-principles"><span className="eyebrow">MANAGER RULES</span><div>• Task-specific capability, not fixed roles</div><div>• Existing employees retain historical performance</div><div>• New employees enter through self-initialization</div><div>• QA employees are independent from the producer</div><div>• Every rework records the exact problem</div><div>• Maximum 3 reworks before escalation</div><div>• Manager owns final acceptance</div></section>
        </aside>
      </div>
    </main>
  );
}
