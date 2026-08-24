from __future__ import annotations
import json, time, urllib.error, urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4
_STORE=Path(__file__).resolve().parent.parent/".nexus_ai_connections.json"
def _load():
    try: data=json.loads(_STORE.read_text(encoding="utf-8")); data.setdefault("connections",[]); return data
    except (FileNotFoundError,json.JSONDecodeError): return {"connections":[]}
def _save(data): _STORE.write_text(json.dumps(data,indent=2),encoding="utf-8")
def _public(x): return {k:v for k,v in x.items() if k!="api_key"}|{"api_key_configured":bool(x.get("api_key")),"connection_ready":x.get("test_status")=="ok","execution_ready":bool(x.get("enabled",True)) and x.get("test_status")=="ok"}
def list_connections(): return [_public(x) for x in _load()["connections"]]
def get_connection(worker_id): return next((x for x in _load()["connections"] if x["worker_id"]==worker_id),None)
def register_connection(*,name,provider,api_key,model,base_url,free_verified=False,capabilities=None):
    name,provider,api_key,model=name.strip(),provider.strip().lower(),api_key.strip(),model.strip(); base_url=base_url.strip().rstrip("/")
    if not all((name,provider,api_key,model,base_url)): raise ValueError("Name, provider, API key, model, and base URL are required.")
    default={"reasoning":75,"research":75,"coding":75,"documents":75,"presentation":70,"data_analysis":70,"instruction_following":80,"reliability":70,"efficiency":70}
    item={"worker_id":f"custom-{uuid4().hex[:10]}","name":name,"provider":provider,"api_key":api_key,"model":model,"base_url":base_url,"free_verified":bool(free_verified),"capabilities":capabilities or default,"enabled":True,"test_status":"untested","last_error":None,"last_error_code":None,"last_error_status":None,"last_latency_ms":None,"last_tested_at":None,"last_diagnostic":None}
    data=_load(); data["connections"].append(item); _save(data); return _public(item)
def delete_connection(worker_id):
    data=_load(); before=len(data["connections"]); data["connections"]=[x for x in data["connections"] if x["worker_id"]!=worker_id]; changed=len(data["connections"])!=before
    if changed:_save(data)
    return changed
def _url(item,path): return f'{item["base_url"].rstrip("/")}/{path.lstrip("/")}'
def _request(url,key,method="GET",payload=None,provider=""):
    headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"}
    if provider=="openrouter": headers.update({"HTTP-Referer":"http://localhost:5173","X-Title":"NEXUS AI Corporate Manager"})
    req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            raw=r.read().decode(errors="replace")
            try:return r.status,json.loads(raw or "{}")
            except json.JSONDecodeError:return r.status,raw
    except urllib.error.HTTPError as e:
        raw=e.read().decode(errors="replace")[:4000]
        try: body=json.loads(raw or "{}")
        except json.JSONDecodeError: body=raw
        return e.code,body
    except urllib.error.URLError as e: raise RuntimeError(f"Network error: {e.reason}") from e
    except TimeoutError as e: raise RuntimeError("Request timed out after 30 seconds") from e
def _error_details(body):
    if isinstance(body,dict):
        e=body.get("error",body)
        if isinstance(e,dict): return (str(e.get("code")) if e.get("code") is not None else None),str(e.get("message") or e)
    return None,str(body)
def _check(name,status,message=None,code=None,**extra):
    d={"name":name,"status":status};
    if message is not None:d["message"]=message
    if code is not None:d["code"]=code
    d.update(extra); return d
def _record(worker_id,status,diagnostic=None,error=None,code=None,http_status=None,latency=None):
    data=_load(); item=next((x for x in data["connections"] if x["worker_id"]==worker_id),None)
    if not item:return
    item.update({"test_status":status,"last_error":error,"last_error_code":code,"last_error_status":http_status,"last_latency_ms":latency,"last_tested_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"last_diagnostic":diagnostic}); _save(data)
def diagnose_connection(worker_id):
    item=get_connection(worker_id)
    if not item: raise ValueError("AI connection not found.")
    if not item.get("api_key"): raise ValueError("API key is not configured.")
    started=time.perf_counter(); base=item["base_url"].rstrip("/"); model=item["model"]; provider=item["provider"]
    result={"provider":provider,"model_name":model,"base_url":base,"endpoint":_check("Endpoint","NOT_TESTED"),"authentication":_check("Authentication","NOT_TESTED"),"model_check":_check("Model","NOT_TESTED",model=model),"completion":_check("Completion","NOT_TESTED"),"overall":"FAILED","latency_ms":None}
    try:
        status,body=_request(f"{base}/models",item["api_key"],provider=provider)
        if status==200:
            result["endpoint"]=_check("Endpoint","PASS",http_status=status)
            result["authentication"]=_check("Authentication","PASS",http_status=status)
            ids=[m.get("id") for m in (body.get("data",[]) if isinstance(body,dict) else []) if isinstance(m,dict) and m.get("id")]
            available=model in ids
            result["model_check"]=_check("Model","PASS" if available else "FAIL",model=model,available=available,available_models=ids[:30])
        else:
            code,msg=_error_details(body); result["endpoint"]=_check("Endpoint","PASS",http_status=status,message="Provider endpoint responded."); result["authentication"]=_check("Authentication","FAIL",http_status=status,code=code,message=msg); return _finish(item,result,started,msg,code,status)
    except Exception as e:
        result["endpoint"]=_check("Endpoint","FAIL",message=str(e)); return _finish(item,result,started,str(e))
    if result["model_check"]["status"]!="PASS":
        msg=f"Model '{model}' is not available from the provider model catalogue."; return _finish(item,result,started,msg,"model_unavailable",200)
    try:
        status,body=_request(_url(item,"chat/completions"),item["api_key"],"POST",{"model":model,"messages":[{"role":"user","content":"Reply with exactly: NEXUS connection is working."}],"max_tokens":128},provider)
        if status!=200:
            code,msg=_error_details(body); result["completion"]=_check("Completion","FAIL",http_status=status,code=code,message=msg); return _finish(item,result,started,msg,code,status)
        choices=body.get("choices",[]) if isinstance(body,dict) else []; text=(choices[0].get("message",{}).get("content","") if choices else "").strip()
        if not text: raise RuntimeError("Completion endpoint returned no text content.")
        result["completion"]=_check("Completion","PASS",http_status=status,response_preview=text[:200]); result["overall"]="PASS"; return _finish(item,result,started)
    except Exception as e: return _finish(item,result,started,str(e))
def _finish(item,result,started,error=None,code=None,http_status=None):
    latency=round((time.perf_counter()-started)*1000,2); result["latency_ms"]=latency
    if error: result["error"]={"message":error,"code":code,"http_status":http_status}
    ok=result["overall"]=="PASS" and not error
    _record(item["worker_id"],"ok" if ok else "failed",result,error,code,http_status,latency)
    return result
def test_connection(worker_id,prompt="Reply with exactly: NEXUS connection is working."): return diagnose_connection(worker_id)
def generate_custom(worker_id,prompt):
    item=get_connection(worker_id)
    if not item: raise ValueError("AI connection not found.")
    if item.get("test_status")!="ok": raise RuntimeError("AI employee is not connection-ready. Run a successful connection diagnostic first.")
    started=time.perf_counter(); status,body=_request(_url(item,"chat/completions"),item["api_key"],"POST",{"model":item["model"],"messages":[{"role":"user","content":prompt}],"max_tokens":1024},item["provider"])
    if status!=200:
        code,msg=_error_details(body); _record(worker_id,"failed",error=msg,code=code,http_status=status,latency=round((time.perf_counter()-started)*1000,2)); raise RuntimeError(f"Execution failed: HTTP {status} [{code}] {msg}")
    choices=body.get("choices",[]) if isinstance(body,dict) else []; text=(choices[0].get("message",{}).get("content","") if choices else "").strip()
    if not text: raise RuntimeError("Provider returned no text content.")
    return {"text":text,"telemetry":{"worker_id":worker_id,"last_latency_ms":round((time.perf_counter()-started)*1000,2),"configured":True,"execution_ready":True}}
