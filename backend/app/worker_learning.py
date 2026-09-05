from __future__ import annotations
import json, math, os, re, tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

_STORE = Path(__file__).resolve().parent.parent / ".nexus_worker_learning.json"
_LOCK = RLock()
_CAPABILITY_TESTS = {
    "reasoning": [{"id":"reasoning_logic_01","metric":"reasoning_accuracy","prompt":"Solve this logic task and give only the final answer plus a one-sentence justification: If all A are B and no B are C, can any A be C?"},{"id":"reasoning_constraints_01","metric":"instruction_adherence","prompt":"Return exactly three numbered items, each containing exactly five words, describing good decision-making."}],
    "research": [{"id":"research_synthesis_01","metric":"research_synthesis","prompt":"Explain how you would research a market-entry decision. Specify evidence types, source-quality checks, conflicting-evidence handling, and a concise synthesis method. Do not invent sources."},{"id":"research_claims_01","metric":"evidence_discipline","prompt":"Give three example business claims and label exactly what evidence would be required to verify each claim. Do not claim the examples are factual."}],
    "data_analysis": [{"id":"data_calculation_01","metric":"calculation_accuracy","prompt":"For sales values 100, 120, 150, 130, 180 calculate the mean, median, maximum and range. Show the calculations."},{"id":"data_interpretation_01","metric":"data_interpretation","prompt":"Using sales values 100, 120, 150, 130, 180, identify one defensible pattern and one conclusion that cannot be established from this data alone."}],
    "documents": [{"id":"documents_completeness_01","metric":"document_completeness","prompt":"Draft a concise executive update with objective, current status, three findings, two risks and three next actions. Clearly label every section."},{"id":"documents_adherence_01","metric":"instruction_adherence","prompt":"Write exactly 80 words explaining why version control matters in a corporate AI workflow."}],
    "coding": [{"id":"coding_logic_01","metric":"coding_correctness","prompt":"Write a Python function named average(values) that returns the arithmetic mean and raises ValueError for an empty list. Include a short test."},{"id":"coding_debug_01","metric":"debugging","prompt":"Identify the bug in: result = total / count; count = 0. Explain the failure and give the corrected approach."}],
    "presentation": [{"id":"presentation_structure_01","metric":"presentation_structure","prompt":"Design a six-slide executive presentation structure for a business expansion recommendation. State the purpose of every slide."}],
    "vision": [{"id":"vision_readiness_01","metric":"vision_readiness","prompt":"You may not have an image in this test. Explain how you would inspect a supplied business image, identify visual evidence, distinguish observation from inference, and report uncertainty."}],
}

def _default_worker(): return {"observations":0,"successes":0,"failures":0,"latencies_ms":[],"quality_passes":0,"quality_reworks":0,"tasks":{},"collaboration":{}}

def _load():
    try:
        d=json.loads(_STORE.read_text(encoding="utf-8")); d.setdefault("workers",{}); d.setdefault("collaboration",{}); d["version"]=max(int(d.get("version",1)),7); return d
    except (FileNotFoundError,json.JSONDecodeError,OSError,TypeError,ValueError): return {"workers":{},"version":7,"collaboration":{}}

def _save(d):
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary=tempfile.mkstemp(prefix=".nexus_worker_learning_",suffix=".tmp",dir=_STORE.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle: json.dump(d,handle,indent=2); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary,_STORE)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)

def record_result(worker_id,*,task_type,success,latency_ms=None,quality=None,quality_score=None):
    with _LOCK:
        d=_load(); w=d.setdefault("workers",{}).setdefault(worker_id,_default_worker()); now=datetime.now(timezone.utc).isoformat()
        w["observations"]+=1; w["successes"]+=int(success); w["failures"]+=int(not success); w["last_observed_at"]=now
        if latency_ms is not None:w["latencies_ms"]=(w.get("latencies_ms",[])+[round(float(latency_ms),2)])[-100:]
        if quality=="PASS":w["quality_passes"]+=1
        elif quality=="REWORK":w["quality_reworks"]+=1
        t=w.setdefault("tasks",{}).setdefault(task_type,{"observations":0,"successes":0,"failures":0,"latencies_ms":[],"quality_passes":0,"quality_reworks":0,"quality_scores":[],"last_observed_at":None}); t["observations"]+=1; t["successes"]+=int(success); t["failures"]+=int(not success); t["last_observed_at"]=now
        if latency_ms is not None:t["latencies_ms"]=(t.get("latencies_ms",[])+[round(float(latency_ms),2)])[-100:]
        if quality=="PASS":t["quality_passes"]+=1
        elif quality=="REWORK":t["quality_reworks"]+=1
        if quality_score is not None:t["quality_scores"]=(t.get("quality_scores",[])+[float(quality_score)])[-100:]
        _save(d)

def get_worker_learning(worker_id):
    with _LOCK:return _load().get("workers",{}).get(worker_id,{})

def task_performance(worker_id,task_type):
    w=get_worker_learning(worker_id); t=w.get("tasks",{}).get(task_type,{}); n=int(t.get("observations",0))
    if not n:return {"score":0.0,"confidence":0.0,"success_rate":0.0,"rework_rate":0.0,"avg_latency_ms":0.0,"observations":0,"quality_score":0.0,"recency_factor":0.0}
    sr=float(t.get("successes",0))/n; reviews=int(t.get("quality_passes",0))+int(t.get("quality_reworks",0)); rr=int(t.get("quality_reworks",0))/reviews if reviews else 0
    lat=t.get("latencies_ms",[]); avg=sum(lat)/len(lat) if lat else 0; qs=t.get("quality_scores",[]); quality=sum(qs)/len(qs) if qs else sr*100
    observed_at=t.get("last_observed_at") or w.get("last_observed_at"); recency=0.0
    if observed_at:
        try: age_days=max(0,(datetime.now(timezone.utc)-datetime.fromisoformat(observed_at.replace("Z","+00:00"))).total_seconds()/86400); recency=round(math.exp(-age_days/30),4)
        except (ValueError,TypeError): recency=0.0
    confidence=round(min(100,20+15*math.log1p(n)+35*recency),2)
    score=max(0,min(100,quality*.55+sr*100*.25+(100-rr*100)*.15+max(0,min(100,100-avg/100))*.05))
    return {"score":round(score,2),"confidence":confidence,"success_rate":round(sr*100,2),"rework_rate":round(rr*100,2),"avg_latency_ms":round(avg,2),"observations":n,"quality_score":round(quality,2),"recency_factor":recency}

def learned_adjustments(worker_id,task_type):
    p=task_performance(worker_id,task_type)
    if not p["observations"]:return {"reliability":0.0,"efficiency":0.0}
    return {"reliability":round((p["success_rate"]-50)*.12,2),"efficiency":round(max(-5,min(5,(3000-p["avg_latency_ms"])/600)),2)}

def collaboration_performance(source_worker_id,support_worker_id,task_type=None):
    with _LOCK:
        data=_load().get("collaboration",{}); key=f"{source_worker_id}:{support_worker_id}:{task_type or '*'}"; item=data.get(key,{})
    n=int(item.get("observations",0)); sr=(float(item.get("successes",0))/n*100) if n else 0.0
    return {"score":round(sr,2),"success_rate":round(sr,2),"observations":n,"confidence":round(min(100,20+15*math.log1p(n)),2) if n else 0.0}

def record_collaboration(source_worker_id,support_worker_id,*,task_type,success):
    with _LOCK:
        d=_load(); key=f"{source_worker_id}:{support_worker_id}:{task_type}"; item=d.setdefault("collaboration",{}).setdefault(key,{"observations":0,"successes":0,"failures":0}); item["observations"]+=1; item["successes"]+=int(success); item["failures"]+=int(not success); _save(d)

def learning_snapshot():
    with _LOCK:return _load()

def _test_capability_for_worker(worker,capability):
    tests=_CAPABILITY_TESTS.get(capability,[]); return {"capability":capability,"test_count":len(tests),"tests":[{"test_id":t["id"],"metric":t["metric"],"prompt":t["prompt"],"status":"ready"} for t in tests]}

def self_initialize():
    from .worker_registry import list_workers
    now=datetime.now(timezone.utc).isoformat(); results=[]
    with _LOCK:
        d=_load()
        for w in list_workers():
            e=d.setdefault("workers",{}).setdefault(w.worker_id,_default_worker())
            if "onboarding" not in e:
                caps=w.capabilities.model_dump(exclude_none=True); app=[n for n,v in caps.items() if v is not None and n in _CAPABILITY_TESTS]; e["onboarding"]={"status":"ready_for_benchmark","initialized_at":now,"initial_capabilities":caps,"benchmark_capabilities":[_test_capability_for_worker(w,c) for c in app],"tests_completed":0,"tests_total":sum(len(_CAPABILITY_TESTS.get(c,[])) for c in app),"note":"Initial capability scores are priors; real task evidence updates task-specific performance."}; action="new_worker_onboarding_created"
            else: action="existing_worker_history_preserved"
            results.append({"worker_id":w.worker_id,"action":action,"onboarding_status":e["onboarding"]["status"],"observations":e.get("observations",0),"tests_completed":e["onboarding"].get("tests_completed",0),"tests_total":e["onboarding"].get("tests_total",0)})
        _save(d)
    return {"status":"initialized","timestamp":now,"workers":results,"policy":"new_workers_get_benchmarks; existing_workers_keep_history"}
