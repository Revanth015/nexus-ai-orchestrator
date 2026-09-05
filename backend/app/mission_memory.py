from __future__ import annotations
import json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

_STORE=Path(__file__).resolve().parent.parent/".nexus_mission_memory.json"; _LOCK=RLock()
_STATES={"PLANNING","ALLOCATING","EXECUTING","COLLABORATING","REVIEWING","REWORKING","MANAGER_REVIEW","COMPLETED","BLOCKED","FAILED","ESCALATED","RESOURCE_EXHAUSTED","REWORK_LIMIT_REACHED"}

def _load():
    try:
        data=json.loads(_STORE.read_text(encoding="utf-8")); data.setdefault("missions",{}); data.setdefault("completed_memory",[]); return data
    except (FileNotFoundError,json.JSONDecodeError,OSError,TypeError): return {"missions":{},"completed_memory":[]}

def _save(data):
    _STORE.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix=".nexus_mission_",suffix=".tmp",dir=_STORE.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle: json.dump(data,handle,indent=2); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp,_STORE)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def create_mission(objective:str,*,success_criteria:list[str]|None=None,resource_budget:int=12):
    if not objective.strip(): raise ValueError("Mission objective cannot be empty.")
    mission_id=f"mission-{uuid4().hex[:12]}"; now=datetime.now(timezone.utc).isoformat(); mission={"mission_id":mission_id,"objective":objective.strip(),"success_criteria":success_criteria or [],"state":"PLANNING","state_history":[],"sprint":1,"current_task_id":None,"tasks":[],"active_workers":[],"artifacts":[],"decisions":[],"collaborations":[],"qa_findings":[],"rework_count":0,"max_reworks":3,"resource_budget":max(1,int(resource_budget)),"resource_used":0.0,"resource_reserved":0.0,"created_at":now,"updated_at":now}
    with _LOCK: data=_load(); data["missions"][mission_id]=mission; _save(data)
    return mission

def get_mission(mission_id):
    with _LOCK:return _load().get("missions",{}).get(mission_id)

def update_mission(mission_id,**changes):
    with _LOCK:
        data=_load(); mission=data.get("missions",{}).get(mission_id)
        if not mission: raise KeyError(f"Mission '{mission_id}' not found.")
        if "state" in changes and changes["state"] not in _STATES: raise ValueError(f"Invalid mission state: {changes['state']}")
        mission.update(changes); mission["updated_at"]=datetime.now(timezone.utc).isoformat(); _save(data); return mission

def transition(mission_id,state,*,reason=None):
    if state not in _STATES: raise ValueError(f"Invalid mission state: {state}")
    mission=get_mission(mission_id)
    if not mission: raise KeyError(f"Mission '{mission_id}' not found.")
    history=list(mission.get("state_history",[])); history.append({"from":mission.get("state"),"to":state,"reason":reason,"timestamp":datetime.now(timezone.utc).isoformat()}); return update_mission(mission_id,state=state,state_history=history)

def add_task(mission_id,task):
    mission=get_mission(mission_id)
    if not mission: raise KeyError(f"Mission '{mission_id}' not found.")
    tasks=list(mission.get("tasks",[])); tasks.append(task); return update_mission(mission_id,tasks=tasks,current_task_id=task.get("task_id"))

def add_artifact(mission_id,artifact):
    mission=get_mission(mission_id)
    if not mission: raise KeyError(f"Mission '{mission_id}' not found.")
    artifacts=list(mission.get("artifacts",[])); artifacts.append(artifact); return update_mission(mission_id,artifacts=artifacts)

def add_decision(mission_id,decision):
    mission=get_mission(mission_id)
    if not mission: raise KeyError(f"Mission '{mission_id}' not found.")
    items=list(mission.get("decisions",[])); items.append(decision); return update_mission(mission_id,decisions=items)

def add_qa_finding(mission_id,finding):
    mission=get_mission(mission_id)
    if not mission: raise KeyError(f"Mission '{mission_id}' not found.")
    items=list(mission.get("qa_findings",[])); items.append(finding); return update_mission(mission_id,qa_findings=items)

def add_collaboration(mission_id,collaboration):
    mission=get_mission(mission_id)
    if not mission: raise KeyError(f"Mission '{mission_id}' not found.")
    items=list(mission.get("collaborations",[])); items.append(collaboration); return update_mission(mission_id,collaborations=items)

def record_resource_use(mission_id,amount:float=1.0):
    mission=get_mission(mission_id); used=float(mission.get("resource_used",0))+max(0,float(amount)); return update_mission(mission_id,resource_used=used)

def reserve_resources(mission_id,amount:float):
    mission=get_mission(mission_id)
    if not mission: raise KeyError(f"Mission '{mission_id}' not found.")
    amount=max(0,float(amount)); used=float(mission.get("resource_used",0)); reserved=float(mission.get("resource_reserved",0)); budget=float(mission.get("resource_budget",0))
    if used+reserved+amount>budget: raise ValueError(f"Resource budget exceeded: required {amount:.1f}, available {max(0,budget-used-reserved):.1f}.")
    return update_mission(mission_id,resource_reserved=reserved+amount)

def consume_reserved_resources(mission_id,amount:float):
    mission=get_mission(mission_id)
    if not mission: raise KeyError(f"Mission '{mission_id}' not found.")
    amount=max(0,float(amount)); reserved=float(mission.get("resource_reserved",0)); used=float(mission.get("resource_used",0)); consumed=min(amount,reserved); return update_mission(mission_id,resource_reserved=reserved-consumed,resource_used=used+consumed)

def release_reserved_resources(mission_id,amount:float):
    mission=get_mission(mission_id)
    if not mission: raise KeyError(f"Mission '{mission_id}' not found.")
    reserved=float(mission.get("resource_reserved",0)); return update_mission(mission_id,resource_reserved=max(0,reserved-max(0,float(amount))))

def complete_mission(mission_id,*,final_decision:str,final_quality:float|None=None):
    mission=get_mission(mission_id)
    if not mission: raise KeyError(f"Mission '{mission_id}' not found.")
    if final_decision!="ACCEPT": raise ValueError("Only an ACCEPT decision can complete a mission.")
    summary={"mission_id":mission_id,"objective":mission["objective"],"sprint":mission.get("sprint",1),"task_count":len(mission.get("tasks",[])),"worker_count":len(set(mission.get("active_workers",[]))),"collaboration_count":len(mission.get("collaborations",[])),"rework_count":mission.get("rework_count",0),"resource_used":mission.get("resource_used",0),"resource_reserved":mission.get("resource_reserved",0),"final_decision":final_decision,"final_quality":final_quality,"completed_at":datetime.now(timezone.utc).isoformat()}
    with _LOCK: data=_load(); data["completed_memory"]=(data.get("completed_memory",[])+[summary])[-1000:]; _save(data)
    transition(mission_id,"COMPLETED",reason=f"Final Manager decision: {final_decision}"); return summary

def recent_memory(*,objective_keyword=None,limit:int=20):
    with _LOCK: items=list(_load().get("completed_memory",[]))
    if objective_keyword: items=[x for x in items if objective_keyword.lower() in x.get("objective","").lower()]
    return items[-max(1,min(limit,100)):]

def memory_snapshot():
    with _LOCK:return _load()
