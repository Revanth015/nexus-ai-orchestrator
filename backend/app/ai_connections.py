from __future__ import annotations
import json,time,urllib.error,urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4
_STORE=Path(__file__).resolve().parent.parent/".nexus_ai_connections.json"
def _load():
    try:
        d=json.loads(_STORE.read_text(encoding="utf-8"));d.setdefault("connections",[]);return d
    except (FileNotFoundError,json.JSONDecodeError):return {"connections":[]}
def _save(d):_STORE.write_text(json.dumps(d,indent=2),encoding="utf-8")
def list_connections():return [{k:v for k,v in x.items() if k!="api_key"}|{"api_key_configured":bool(x.get("api_key"))} for x in _load()["connections"]]
def get_connection(worker_id):return next((x for x in _load()["connections"] if x["worker_id"]==worker_id),None)
def register_connection(*,name,provider,api_key,model,base_url,free_verified=False,capabilities=None):
    name=name.strip();provider=provider.strip().lower();api_key=api_key.strip();model=model.strip();base_url=base_url.strip().rstrip("/")
    if not name or not provider or not api_key or not model or not base_url:raise ValueError("Name, provider, API key, model, and base URL are required.")
    default={"reasoning":75,"research":75,"coding":75,"documents":75,"presentation":70,"data_analysis":70,"instruction_following":80,"reliability":70,"efficiency":70}
    worker_id=f"custom-{uuid4().hex[:10]}";item={"worker_id":worker_id,"name":name,"provider":provider,"api_key":api_key,"model":model,"base_url":base_url,"free_verified":bool(free_verified),"capabilities":capabilities or default,"enabled":True};d=_load();d["connections"].append(item);_save(d);return {k:v for k,v in item.items() if k!="api_key"}|{"api_key_configured":True}
def delete_connection(worker_id):
    d=_load();before=len(d["connections"]);d["connections"]=[x for x in d["connections"] if x["worker_id"]!=worker_id];changed=len(d["connections"])!=before
    if changed:_save(d)
    return changed
def _post(url,key,payload):
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=90) as r:return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as exc:raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:500]}") from exc
def test_connection(worker_id,prompt="Reply with exactly: NEXUS connection is working."):
    item=get_connection(worker_id)
    if not item:raise ValueError("AI connection not found.")
    if not item.get("api_key"):raise ValueError("API key is not configured.")
    started=time.perf_counter();url=item["base_url"] if item["base_url"].endswith("/chat/completions") else item["base_url"]+"/chat/completions"
    try:
        data=_post(url,item["api_key"],{"model":item["model"],"messages":[{"role":"user","content":prompt}],"max_tokens":128});text=data.get("choices",[{}])[0].get("message",{}).get("content","").strip()
        if not text:raise RuntimeError("Provider returned no text content.")
        return {"status":"ok","text":text,"latency_ms":round((time.perf_counter()-started)*1000,2)}
    except Exception as exc:raise RuntimeError(f"Connection test failed: {exc}") from exc
def generate_custom(worker_id,prompt):
    r=test_connection(worker_id,prompt);return {"text":r["text"],"telemetry":{"worker_id":worker_id,"last_latency_ms":r["latency_ms"],"configured":True,"execution_ready":True}}
