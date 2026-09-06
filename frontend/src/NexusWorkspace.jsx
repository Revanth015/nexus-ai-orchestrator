import React, { useEffect, useRef, useState } from "react";
import { BrainCircuit, ChevronDown, MessageSquarePlus, Paperclip, Pencil, Plus, Send, Settings, Trash2, X, Sparkles } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const AUTO = "__auto__";
const emptyForm = { name: "", provider: "OpenAI-compatible", api_key: "", model: "", base_url: "", free_verified: false };

function connectionState(worker) {
  if (worker?.execution_ready) return "Connected";
  if (worker?.api_key_configured && worker?.test_status === "failed") return "Needs attention";
  if (worker?.api_key_configured) return "Not tested";
  return "Not configured";
}

export default function NexusWorkspace() {
  const [workers, setWorkers] = useState([]);
  const [selectedWorker, setSelectedWorker] = useState(AUTO);
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [showConnections, setShowConnections] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [busy, setBusy] = useState(false);
  const [diagnosing, setDiagnosing] = useState({});
  const [diagnoses, setDiagnoses] = useState({});
  const fileInputRef = useRef(null);
  const [files, setFiles] = useState([]);

  const loadWorkers = async () => {
    try {
      const response = await fetch(`${API_BASE}/workers`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load AIs");
      const list = data.workers ?? [];
      setWorkers(list);
      setSelectedWorker(current => current === AUTO || list.some(w => w.worker_id === current) ? current : AUTO);
    } catch (e) { setError(e.message || "Could not load AIs"); }
  };
  useEffect(() => { loadWorkers(); }, []);

  const openAdd = () => { setEditing(null); setForm(emptyForm); setShowForm(true); setError(""); };
  const openEdit = worker => {
    setEditing(worker);
    setForm({ name: worker.name ?? "", provider: worker.provider ?? "OpenAI-compatible", api_key: "", model: worker.metadata?.model ?? worker.model ?? "", base_url: worker.metadata?.base_url ?? worker.base_url ?? "", free_verified: !!worker.free_verified });
    setShowForm(true); setError("");
  };
  const saveConnection = async event => {
    event.preventDefault(); if (busy) return; setBusy(true); setError("");
    try {
      const editingId = editing?.worker_id; const payload = { ...form }; if (editingId && !payload.api_key) delete payload.api_key;
      const response = await fetch(`${API_BASE}/workers/connections${editingId ? `/${editingId}` : ""}`, { method: editingId ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const data = await response.json(); if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not save AI connection");
      setShowForm(false); setEditing(null); setForm(emptyForm); await loadWorkers();
    } catch (e) { setError(e.message || "Could not save AI connection"); } finally { setBusy(false); }
  };
  const diagnose = async worker => {
    setDiagnosing(s => ({ ...s, [worker.worker_id]: true })); setError("");
    try { const response = await fetch(`${API_BASE}/workers/connections/${worker.worker_id}/diagnose`, { method: "POST" }); const data = await response.json(); if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Diagnosis failed"); setDiagnoses(d => ({ ...d, [worker.worker_id]: data })); await loadWorkers(); }
    catch (e) { setError(e.message || "Diagnosis failed"); } finally { setDiagnosing(s => ({ ...s, [worker.worker_id]: false })); }
  };
  const removeConnection = async worker => {
    if (!window.confirm(`Remove ${worker.name}?`)) return;
    try { const response = await fetch(`${API_BASE}/workers/connections/${worker.worker_id}`, { method: "DELETE" }); if (!response.ok) { const data = await response.json(); throw new Error(data.detail || "Could not remove AI"); } await loadWorkers(); }
    catch (e) { setError(e.message || "Could not remove AI"); }
  };
  const upload = async selected => {
    if (!selected?.length) return;
    try { for (const file of Array.from(selected)) { const body = new FormData(); body.append("file", file); const response = await fetch(`${API_BASE}/files/upload`, { method: "POST", body }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || "File upload failed"); setFiles(current => [...current, data.file]); } }
    catch (e) { setError(e.message || "File upload failed"); } finally { if (fileInputRef.current) fileInputRef.current.value = ""; }
  };
  const send = async event => {
    event.preventDefault(); const text = prompt.trim(); if (!text || running) return;
    const worker = selectedWorker === AUTO ? null : workers.find(w => w.worker_id === selectedWorker);
    if (selectedWorker !== AUTO && !worker) { setError("Selected AI is no longer available. Choose Auto or another AI."); return; }
    setRunning(true); setError(""); setPrompt("");
    setMessages(current => [...current, { role: "user", content: text, worker: worker?.name ?? "NEXUS Manager", files: files.map(f => f.filename) }]);
    try {
      const body = { task_type: "general_reasoning", prompt: text, file_ids: files.map(f => f.file_id), allow_fallback: true };
      if (worker) body.forced_worker_id = worker.worker_id;
      const response = await fetch(`${API_BASE}/execute`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await response.json(); if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "AI request failed");
      setMessages(current => [...current, { role: "assistant", content: data.output, worker: data.worker_name, fallback: data.fallback_used, attempts: data.attempts, route: data.routing_policy }]);
      setFiles([]);
    } catch (e) { setError(e.message || "AI request failed"); }
    finally { setRunning(false); }
  };
  const selected = workers.find(w => w.worker_id === selectedWorker);

  return <main className="nexus-workspace">
    <header className="workspace-topbar"><div className="workspace-brand"><span className="workspace-logo"><BrainCircuit size={21} /></span><div><strong>NEXUS</strong><small>AI WORKSPACE</small></div></div><div className="workspace-actions"><button onClick={() => setShowConnections(true)}><Settings size={16} /> AI connections <span>{workers.length}</span></button></div></header>
    <div className="workspace-body">
      <aside className="workspace-sidebar"><button className="new-chat" onClick={() => setMessages([])}><MessageSquarePlus size={17} /> New chat</button><div className="sidebar-label">AI WORKFORCE</div>
        <button className={`model-item ${selectedWorker === AUTO ? "active" : ""}`} onClick={() => setSelectedWorker(AUTO)}><span className="model-dot online" /><span><strong>NEXUS Auto</strong><small>Manager selects the best available AI</small></span><Sparkles size={14} /></button>
        {workers.length === 0 && <div className="empty-sidebar">Add an AI to start working.</div>}
        {workers.map(worker => <button key={worker.worker_id} className={`model-item ${selectedWorker === worker.worker_id ? "active" : ""}`} onClick={() => setSelectedWorker(worker.worker_id)}><span className={`model-dot ${worker.execution_ready ? "online" : ""}`} /><span><strong>{worker.name}</strong><small>{worker.model ?? worker.metadata?.model ?? "Model"}</small></span></button>)}
        <button className="add-ai-link" onClick={openAdd}><Plus size={16} /> Add AI</button>
      </aside>
      <section className="workspace-chat">
        {messages.length === 0 ? <div className="welcome"><div className="welcome-icon"><BrainCircuit size={28} /></div><h1>Work with your AIs.</h1><p>Use Auto to let NEXUS choose an execution-ready AI, or select a specific employee when you want direct control.</p>{workers.length === 0 && <button onClick={openAdd}><Plus size={16} /> Connect your first AI</button>}</div> : <div className="message-list">{messages.map((message, index) => <article className={`message ${message.role}`} key={index}><div className="message-meta">{message.role === "user" ? "You" : message.worker}{message.files?.length ? ` · ${message.files.join(", ")}` : ""}</div><div className="message-content">{message.content}</div>{message.role === "assistant" && <small className="fallback-note">{message.fallback ? `NEXUS switched to ${message.worker} after a failed attempt.` : message.route === "automatic_task_routing" ? `NEXUS routed this task to ${message.worker}.` : "Direct allocation"}</small>}</article>)}</div>}
        <form className="chat-composer" onSubmit={send}>
          {files.length > 0 && <div className="composer-files">{files.map(file => <span key={file.file_id}>{file.filename}<button type="button" onClick={() => setFiles(current => current.filter(f => f.file_id !== file.file_id))}><X size={12} /></button></span>)}</div>}
          <textarea value={prompt} onChange={e => setPrompt(e.target.value)} placeholder={selectedWorker === AUTO ? "Ask NEXUS to choose the right AI..." : selected ? `Ask ${selected.name} anything...` : "Connect an AI to start..."} rows={3} disabled={running} />
          <div className="composer-footer"><input ref={fileInputRef} type="file" hidden accept=".csv,.xlsx,.xlsm,.pdf,.txt" multiple onChange={e => upload(e.target.files)} /><button type="button" className="icon-button" onClick={() => fileInputRef.current?.click()} title="Attach file"><Paperclip size={17} /></button><div className="model-select"><ChevronDown size={14} /><select value={selectedWorker} onChange={e => setSelectedWorker(e.target.value)}><option value={AUTO}>NEXUS Auto · Smart routing</option>{workers.map(w => <option value={w.worker_id} key={w.worker_id}>{w.name} · {w.model ?? w.metadata?.model ?? "model"}</option>)}</select></div><button className="send-button" disabled={!prompt.trim() || running || (selectedWorker !== AUTO && !selectedWorker)}>{running ? "Working..." : <><Send size={16} /> Send</>}</button></div>
        </form>
      </section>
    </div>
    {error && <div className="workspace-error">{error}<button onClick={() => setError("")}><X size={14} /></button></div>}
    {showConnections && <div className="modal-backdrop" onMouseDown={e => e.target === e.currentTarget && setShowConnections(false)}><section className="connections-panel"><header><div><span className="sidebar-label">AI LIBRARY</span><h2>Your connections</h2></div><button onClick={() => setShowConnections(false)}><X size={18} /></button></header><div className="connection-list">{workers.filter(w => w.metadata?.custom).map(worker => { const diagnosis = diagnoses[worker.worker_id]; return <div className="connection-card" key={worker.worker_id}><div className="connection-main"><span className={`model-dot ${worker.execution_ready ? "online" : ""}`} /><div><strong>{worker.name}</strong><small>{worker.provider} · {worker.model ?? worker.metadata?.model}</small><span className="connection-state">{connectionState(worker)}</span></div></div><div className="connection-actions"><button onClick={() => diagnose(worker)} disabled={diagnosing[worker.worker_id]}>{diagnosing[worker.worker_id] ? "Testing..." : "Test"}</button><button onClick={() => openEdit(worker)} title="Edit"><Pencil size={15} /></button><button onClick={() => removeConnection(worker)} title="Remove"><Trash2 size={15} /></button></div>{diagnosis && <div className={`diagnosis ${diagnosis.overall === "PASS" ? "pass" : "issue"}`}><strong>Connection {diagnosis.overall}</strong><span>Endpoint {diagnosis.endpoint}</span><span>Auth {diagnosis.authentication}</span><span>Model {diagnosis.model_status}</span><span>Completion {diagnosis.completion_status}</span>{diagnosis.http_status && <span>HTTP {diagnosis.http_status}</span>}{diagnosis.error && <small>{diagnosis.error}</small>}</div>}</div>})}<button className="add-connection" onClick={openAdd}><Plus size={17} /> Add AI connection</button></div></section></div>}
    {showForm && <div className="modal-backdrop" onMouseDown={e => e.target === e.currentTarget && setShowForm(false)}><form className="ai-form" onSubmit={saveConnection}><header><div><span className="sidebar-label">CONNECTION</span><h2>{editing ? "Edit AI" : "Add AI"}</h2></div><button type="button" onClick={() => setShowForm(false)}><X size={18} /></button></header><label>Name<input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="My Claude" required /></label><label>Provider<input value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value })} placeholder="OpenRouter" required /></label><label>API key<input type="password" value={form.api_key} onChange={e => setForm({ ...form, api_key: e.target.value })} placeholder={editing ? "Leave blank to keep existing key" : "Paste API key"} required={!editing} /></label><label>Model<input value={form.model} onChange={e => setForm({ ...form, model: e.target.value })} placeholder="model-name" required /></label><label>Base URL<input value={form.base_url} onChange={e => setForm({ ...form, base_url: e.target.value })} placeholder="https://api.example.com/v1" required /></label><label className="check-row"><input type="checkbox" checked={form.free_verified} onChange={e => setForm({ ...form, free_verified: e.target.checked })} /> I verified this model is free to use</label><button className="save-button" disabled={busy}>{busy ? "Saving..." : editing ? "Update connection" : "Connect AI"}</button></form></div>}
  </main>;
}
