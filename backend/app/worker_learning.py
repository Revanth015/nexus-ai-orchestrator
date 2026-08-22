from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

_STORE = Path(__file__).resolve().parent.parent / ".nexus_worker_learning.json"
_LOCK = Lock()

_CAPABILITY_TESTS = {
    "reasoning": [
        {"id":"reasoning_logic_01","metric":"reasoning_accuracy","prompt":"Solve this logic task and give only the final answer plus a one-sentence justification: If all A are B and no B are C, can any A be C?"},
        {"id":"reasoning_constraints_01","metric":"instruction_adherence","prompt":"Return exactly three numbered items, each containing exactly five words, describing good decision-making."}],
    "research": [
        {"id":"research_synthesis_01","metric":"research_synthesis","prompt":"Explain how you would research a market-entry decision. Specify evidence types, source-quality checks, conflicting-evidence handling, and a concise synthesis method. Do not invent sources."},
        {"id":"research_claims_01","metric":"evidence_discipline","prompt":"Give three example business claims and label exactly what evidence would be required to verify each claim. Do not claim the examples are factual."}],
    "data_analysis": [
        {"id":"data_calculation_01","metric":"calculation_accuracy","prompt":"For sales values 100, 120, 150, 130, 180 calculate the mean, median, maximum and range. Show the calculations."},
        {"id":"data_interpretation_01","metric":"data_interpretation","prompt":"Using sales values 100, 120, 150, 130, 180, identify one defensible pattern and one conclusion that cannot be established from this data alone."}],
    "documents": [
        {"id":"documents_completeness_01","metric":"document_completeness","prompt":"Draft a concise executive update with objective, current status, three findings, two risks and three next actions. Clearly label every section."},
        {"id":"documents_adherence_01","metric":"instruction_adherence","prompt":"Write exactly 80 words explaining why version control matters in a corporate AI workflow."}],
    "coding": [
        {"id":"coding_logic_01","metric":"coding_correctness","prompt":"Write a Python function named average(values) that returns the arithmetic mean and raises ValueError for an empty list. Include a short test."},
        {"id":"coding_debug_01","metric":"debugging","prompt":"Identify the bug in: result = total / count; count = 0. Explain the failure and give the corrected approach."}],
    "presentation": [{"id":"presentation_structure_01","metric":"presentation_structure","prompt":"Design a six-slide executive presentation structure for a business expansion recommendation. State the purpose of every slide."}],
    "vision": [{"id":"vision_readiness_01","metric":"vision_readiness","prompt":"You may not have an image in this test. Explain how you would inspect a supplied business image, identify visual evidence, distinguish observation from inference, and report uncertainty."}],
}


def _default_worker() -> dict[str, Any]:
    return {"observations":0,"successes":0,"failures":0,"latencies_ms":[],"quality_passes":0,"quality_reworks":0,"tasks":{},"collaboration":{}}


def _load() -> dict[str, Any]:
    try:
        data=json.loads(_STORE.read_text(encoding="utf-8")); data.setdefault("workers",{}); data.setdefault("collaboration",{}); data["version"]=max(int(data.get("version",1)),6); return data
    except (FileNotFoundError,json.JSONDecodeError): return {"workers":{},"version":6,"collaboration":{}}


def _save(data: dict[str, Any]) -> None: _STORE.write_text(json.dumps(data,indent=2),encoding="utf-8")


def record_result(worker_id: str, *, task_type: str, success: bool, latency_ms: float|None=None, quality: str|None=None, quality_score: float|None=None) -> None:
    with _LOCK:
        data=_load(); worker=data.setdefault("workers",{}).setdefault(worker_id,_default_worker()); worker["observations"]+=1; worker["successes"]+=int(success); worker["failures"]+=int(not success)
        if latency_ms is not None: worker["latencies_ms"]=(worker.get("latencies_ms",[])+[round(float(latency_ms),2)])[-100:]
        if quality=="PASS": worker["quality_passes"]+=1
        elif quality=="REWORK": worker["quality_reworks"]+=1
        task=worker.setdefault("tasks",{}).setdefault(task_type,{"observations":0,"successes":0,"failures":0,"latencies_ms":[],"quality_passes":0,"quality_reworks":0,"quality_scores":[],"last_observed_at":None})
        task["observations"]+=1; task["successes"]+=int(success); task["failures"]+=int(not success); task["last_observed_at"]=datetime.now(timezone.utc).isoformat()
        if latency_ms is not None: task["latencies_ms"]=(task.get("latencies_ms",[])+[round(float(latency_ms),2)])[-100:]
        if quality=="PASS": task["quality_passes"]+=1
        elif quality=="REWORK": task["quality_reworks"]+=1
        if quality_score is not None: task["quality_scores"]=(task.get("quality_scores",[])+[float(quality_score)])[-100:]
        worker["last_observed_at"]=datetime.now(timezone.utc).isoformat(); _save(data)


def record_collaboration(source_worker_id: str, support_worker_id: str, *, task_type: str, success: bool, latency_ms: float|None=None, value_score: float|None=None) -> None:
    with _LOCK:
        data=_load(); key=f"{source_worker_id}::{support_worker_id}"; pair=data.setdefault("collaboration",{}).setdefault(key,{"source_worker_id":source_worker_id,"support_worker_id":support_worker_id,"observations":0,"successes":0,"failures":0,"value_scores":[],"tasks":{}})
        pair["observations"]+=1; pair["successes"]+=int(success); pair["failures"]+=int(not success)
        if value_score is not None: pair["value_scores"]=(pair.get("value_scores",[])+[float(value_score)])[-100:]
        if latency_ms is not None: pair["last_latency_ms"]=round(float(latency_ms),2)
        task=pair.setdefault("tasks",{}).setdefault(task_type,{"observations":0,"successes":0,"failures":0,"value_scores":[]}); task["observations"]+=1; task["successes"]+=int(success); task["failures"]+=int(not success)
        if value_score is not None: task["value_scores"]=(task.get("value_scores",[])+[float(value_score)])[-100:]
        _save(data)


def get_worker_learning(worker_id: str) -> dict[str, Any]:
    with _LOCK: return _load().get("workers",{}).get(worker_id,{})


def task_performance(worker_id: str, task_type: str) -> dict[str,float]:
    worker=get_worker_learning(worker_id); task=worker.get("tasks",{}).get(task_type,{}); n=int(task.get("observations",0))
    if not n: return {"score":0.0,"confidence":0.0,"success_rate":0.0,"rework_rate":0.0,"avg_latency_ms":0.0,"observations":0,"quality_score":0.0,"recency_factor":0.0}
    success_rate=task.get("successes",0)/n; reviewed=int(task.get("quality_passes",0))+int(task.get("quality_reworks",0)); rework_rate=int(task.get("quality_reworks",0))/reviewed if reviewed else 0.0
    lat=task.get("latencies_ms",[]); avg_latency=sum(lat)/len(lat) if lat else 0.0; qs=task.get("quality_scores",[]); quality=sum(qs)/len(qs) if qs else success_rate*100
    last=task.get("last_observed_at"); age_days=999 if not last else max(0,(datetime.now(timezone.utc)-datetime.fromisoformat(last.replace("Z","+00:00"))).total_seconds()/86400); recency=math.exp(-age_days/30) if age_days<999 else 0.0
    score=max(0,min(100,quality*.55+success_rate*100*.25+(100-rework_rate*100)*.15+max(0,min(100,100-avg_latency/100))*.05))
    # Confidence grows with evidence, but recency and consistency matter too.
    sample_conf=1-math.exp(-n/12); consistency=max(0,1-min(1,(task.get("failures",0)/n)*1.5)); confidence=min(100,(sample_conf*.65+recency*.20+consistency*.15)*100)
    return {"score":round(score,2),"confidence":round(confidence,2),"success_rate":round(success_rate*100,2),"rework_rate":round(rework_rate*100,2),"avg_latency_ms":round(avg_latency,2),"observations":n,"quality_score":round(quality,2),"recency_factor":round(recency,4)}


def learned_adjustments(worker_id: str, task_type: str) -> dict[str,float]:
    p=task_performance(worker_id,task_type)
    if not p["observations"]: return {"reliability":0.0,"efficiency":0.0}
    return {"reliability":(p["success_rate"]-50)*.12,"efficiency":max(-5,min(5,(3000-p["avg_latency_ms"])/600))}


def collaboration_performance(source_worker_id: str, support_worker_id: str, task_type: str|None=None) -> dict[str,float]:
    with _LOCK: data=_load()
    pair=data.get("collaboration",{}).get(f"{source_worker_id}::{support_worker_id}",{})
    obj=pair.get("tasks",{}).get(task_type,{}) if task_type else pair
    n=int(obj.get("observations",0)); success=obj.get("successes",0)/n*100 if n else 0; vals=obj.get("value_scores",[]); value=sum(vals)/len(vals) if vals else success
    return {"score":round(value,2),"success_rate":round(success,2),"observations":n,"confidence":round(min(100,(1-math.exp(-n/10))*100),2)}


def learning_snapshot() -> dict[str,Any]:
    with _LOCK: return _load()


def _test_capability_for_worker(worker, capability: str) -> dict[str,Any]:
    tests=_CAPABILITY_TESTS.get(capability,[]); return {"capability":capability,"test_count":len(tests),"tests":[{"test_id":t["id"],"metric":t["metric"],"prompt":t["prompt"],"status":"ready"} for t in tests]}


def self_initialize() -> dict[str,Any]:
    from .worker_registry import list_workers
    now=datetime.now(timezone.utc).isoformat(); results=[]
    with _LOCK:
        data=_load()
        for worker in list_workers():
            existing=data.setdefault("workers",{}).setdefault(worker.worker_id,_default_worker())
            if "onboarding" not in existing:
                caps=worker.capabilities.model_dump(exclude_none=True); applicable=[name for name,value in caps.items() if value is not None and name in _CAPABILITY_TESTS]
                existing["onboarding"]={"status":"ready_for_benchmark","initialized_at":now,"initial_capabilities":caps,"benchmark_capabilities":[_test_capability_for_worker(worker,c) for c in applicable],"tests_completed":0,"tests_total":sum(len(_CAPABILITY_TESTS.get(c,[])) for c in applicable),"note":"Initial capability scores are priors; real task evidence updates task-specific performance."}; action="new_worker_onboarding_created"
            else: action="existing_worker_history_preserved"
            results.append({"worker_id":worker.worker_id,"action":action,"onboarding_status":existing["onboarding"]["status"],"observations":existing.get("observations",0),"tests_completed":existing["onboarding"].get("tests_completed",0),"tests_total":existing["onboarding"].get("tests_total",0)})
        _save(data)
    return {"status":"initialized","timestamp":now,"workers":results,"policy":"new_workers_get_benchmarks; existing_workers_keep_history"}


def _evaluate(test_id: str, text: str) -> tuple[float,list[str]]:
    text=text.strip(); lower=text.lower(); checks=[]
    if test_id=="reasoning_logic_01": checks=["no" in lower and "a" in lower and "c" in lower]
    elif test_id=="reasoning_constraints_01": lines=[x.strip() for x in text.splitlines() if x.strip()]; checks=[len(lines)==3,all(len(re.findall(r"\b\w+\b",x))==5 for x in lines)]
    elif test_id=="research_synthesis_01": checks=[all(k in lower for k in ["evidence","source","conflict"]),"not invent" in lower or "do not invent" in lower]
    elif test_id=="research_claims_01": checks=[len(re.findall(r"(?:^|\n)\s*(?:1|2|3)[.)]",text))>=3,"evidence" in lower]
    elif test_id=="data_calculation_01": checks=["136" in text,"130" in text,"180" in text,"80" in text]
    elif test_id=="data_interpretation_01": checks=["pattern" in lower or "trend" in lower,"cannot" in lower or "cannot establish" in lower]
    elif test_id=="documents_completeness_01": checks=[all(k in lower for k in ["objective","status","findings","risks","next actions"])]
    elif test_id=="documents_adherence_01": checks=[len(re.findall(r"\b\w+\b",text))==80]
    elif test_id=="coding_logic_01": checks=["def average" in lower,"valueerror" in lower,"return" in lower]
    elif test_id=="coding_debug_01": checks=["zero" in lower or "zerodivision" in lower,"count = 0" in lower or "count=0" in lower]
    elif test_id=="presentation_structure_01": checks=[len(re.findall(r"(?:^|\n)\s*(?:slide\s*)?\d+[.:)]",lower))>=6]
    elif test_id=="vision_readiness_01": checks=[all(k in lower for k in ["observation","inference","uncertainty"])]
    else: checks=[bool(text)]
    score=round(sum(checks)/len(checks)*100,2) if checks else 0.0; return score,[f"check_{i+1}:{'pass' if ok else 'fail'}" for i,ok in enumerate(checks)]


def run_self_initialization(worker_ids: list[str]|None=None, force: bool=False) -> dict[str,Any]:
    from .worker_registry import list_workers
    from .gemini_connector import generate_text as generate_gemini
    from .ai_connectors import generate_claude,generate_perplexity
    self_initialize(); selected=set(worker_ids or []); results=[]; now=datetime.now(timezone.utc).isoformat()
    data=_load()
    for worker in list_workers():
        if selected and worker.worker_id not in selected: continue
        if worker.worker_id not in {"gemini","claude","perplexity"}: continue
        profile=data.get("workers",{}).get(worker.worker_id,{}); onboarding=profile.get("onboarding",{})
        if onboarding.get("status")=="completed" and not force: results.append({"worker_id":worker.worker_id,"status":"skipped_existing_benchmark","reason":"existing worker history preserved"}); continue
        if not worker.metadata.get("execution_ready"): results.append({"worker_id":worker.worker_id,"status":"skipped_not_execution_ready"}); continue
        tests=[]
        for capability in onboarding.get("benchmark_capabilities",[]):
            for test in capability.get("tests",[]):
                try:
                    response=generate_gemini(test["prompt"]) if worker.worker_id=="gemini" else generate_claude(test["prompt"]) if worker.worker_id=="claude" else generate_perplexity(test["prompt"]); score,checks=_evaluate(test["test_id"],response.get("text","")); tests.append({"test_id":test["test_id"],"capability":capability["capability"],"metric":test["metric"],"status":"completed","score":score,"checks":checks,"latency_ms":response.get("telemetry",{}).get("last_latency_ms") or response.get("latency_ms")})
                except Exception as exc: tests.append({"test_id":test["test_id"],"capability":capability["capability"],"metric":test["metric"],"status":"failed","score":0.0,"error":str(exc)[:300]})
        data=_load(); profile=data["workers"].setdefault(worker.worker_id,_default_worker()); ob=profile.setdefault("onboarding",onboarding); ob["status"]="completed" if tests and all(t["status"]=="completed" for t in tests) else "partial"; ob["completed_at"]=now; ob["tests"]=tests; ob["tests_completed"]=sum(t["status"]=="completed" for t in tests); by_cap={}
        for t in tests: by_cap.setdefault(t["capability"],[]).append(t["score"])
        ob["benchmark_scores"]={cap:round(sum(vals)/len(vals),2) for cap,vals in by_cap.items()}; _save(data); results.append({"worker_id":worker.worker_id,"status":ob["status"],"tests_completed":ob["tests_completed"],"tests_total":ob.get("tests_total",len(tests)),"benchmark_scores":ob["benchmark_scores"],"tests":tests})
    return {"status":"completed","timestamp":now,"results":results,"policy":"benchmarks initialize new workers; production history remains authoritative after onboarding"}
