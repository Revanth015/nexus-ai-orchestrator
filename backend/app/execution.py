from __future__ import annotations

import re
from typing import Callable
from pydantic import BaseModel, Field
from .files_service import read_file
from .local_workers import execute_local_task
from .manager_decision import manager_decide
from .planner import analyze_prompt, build_task_plan
from .providers import generate_claude, generate_perplexity, generate_text
from .router import route_task
from .worker_registry import record_result, task_performance
from .ai_connections import generate_custom

_TASK_METRICS = {"research": (65, 55), "file_analysis": (60, 60), "data_analysis": (70, 65), "presentation": (55, 50), "quality_review": (60, 75), "writing": (45, 45), "image_generation": (40, 35), "coding": (75, 70), "general_reasoning": (50, 55)}

class ExecutionRequest(BaseModel):
    task_type: str; prompt: str; file_ids: list[str] = Field(default_factory=list); forced_worker_id: str | None = None; excluded_worker_ids: list[str] = Field(default_factory=list)
class ExecutionResponse(BaseModel):
    status: str; task_type: str; worker_id: str; worker_name: str; routing_policy: str; route_score: float; output: str; telemetry: dict
class MissionExecutionRequest(BaseModel):
    prompt: str; file_ids: list[str] = Field(default_factory=list); resource_budget: int = 12
class ArtifactRecord(BaseModel):
    artifact_id: str; task_id: str; name: str; artifact_type: str; content: str; size_chars: int; preview: str
class TaskExecutionRecord(BaseModel):
    task_id: str; task_type: str; title: str; status: str; worker_id: str | None = None; worker_name: str | None = None; output: str | None = None; route_score: float | None = None; telemetry: dict = Field(default_factory=dict); artifact_ids: list[str] = Field(default_factory=list); collaborators: list[str] = Field(default_factory=list); candidate_worker_ids: list[str] = Field(default_factory=list); manager_confidence: float | None = None; manager_estimated_value: float | None = None; manager_resource_cost: float | None = None; manager_decision: str | None = None; manager_rationale: str | None = None; quality_decision: str | None = None; quality_score: float | None = None; review_recommendation: str | None = None; rework_number: int = 0; rework_problem: str | None = None; sprint: int = 1; error: str | None = None
class MissionExecutionResponse(BaseModel):
    status: str; objective: str; execution_order: list[str]; manager_decision: str; rework_count: int; max_reworks: int; tasks: list[TaskExecutionRecord]; artifacts: list[ArtifactRecord]
class ManagerExecutionDecision(BaseModel):
    action: str; rationale: str; confidence: float; estimated_value: float; resource_cost: float; verification_required: bool; collaboration_required: bool; selected_worker_id: str | None = None; collaborator_worker_ids: list[str] = Field(default_factory=list); candidate_worker_ids: list[str] = Field(default_factory=list)

def _task_complexity(task_type: str, prompt: str) -> float:
    base = _TASK_METRICS.get(task_type, (50, 50))[0]; text = prompt.lower(); bonus = min(20, len(text) / 500)
    if any(x in text for x in ("multiple", "compare", "optimize", "strategy", "integrate", "forecast")): bonus += 10
    return min(100, base + bonus)
def _quality_risk(task_type: str, prompt: str) -> float:
    base = _TASK_METRICS.get(task_type, (50, 50))[1]
    if any(x in prompt.lower() for x in ("financial", "medical", "legal", "safety", "critical", "ceo", "decision")): base += 15
    return min(100, base)
def decide_worker_for_task(task_type: str, *, prompt: str = "", free_only: bool = True, budget_remaining: int = 10, exclude_worker_ids: set[str] | None = None) -> ManagerExecutionDecision:
    route = route_task(task_type, free_only=free_only, exclude_worker_ids=exclude_worker_ids); candidates = [c for c in route.candidates if c.execution_ready and c.eligible_for_task]; ids = [c.worker_id for c in candidates]
    if not candidates: return ManagerExecutionDecision(action="STOP", rationale=f"No execution-ready worker is available for {task_type} after applying Manager exclusions.", confidence=0, estimated_value=0, resource_cost=0, verification_required=False, collaboration_required=False, candidate_worker_ids=ids)
    evidence = [(c, task_performance(c.worker_id, task_type)) for c in candidates]; best, performance = max(evidence, key=lambda item: (item[1].get("score", 0), item[1].get("confidence", 0), item[0].score)); complexity = _task_complexity(task_type, prompt); risk = _quality_risk(task_type, prompt); confidence = float(performance.get("confidence", 0)); collaboration_score = 0.0
    if len(candidates) > 1:
        second = sorted(candidates, key=lambda c: c.score, reverse=True)[1]; collaboration_score = max(0.0, min(100.0, 50.0 - abs(best.score - second.score) + second.capability_score * 0.5))
    decision = manager_decide(task_type=task_type, complexity=complexity, confidence=confidence, quality_risk=risk, worker_score=performance.get("score", 0), collaboration_score=collaboration_score, latency_ms=performance.get("avg_latency_ms", 0), budget_remaining=budget_remaining, evidence_gap=100-confidence); collaborators=[]
    if decision.collaboration_required and len(candidates)>1: collaborators=[c.worker_id for c in sorted(candidates,key=lambda c:c.score,reverse=True) if c.worker_id != best.worker_id][:1]
    return ManagerExecutionDecision(action=decision.action, rationale=decision.rationale, confidence=decision.confidence, estimated_value=decision.estimated_value, resource_cost=decision.resource_cost, verification_required=decision.verification_required, collaboration_required=decision.collaboration_required, selected_worker_id=None if decision.action=="STOP" else best.worker_id, collaborator_worker_ids=collaborators, candidate_worker_ids=ids)

def _load_files(file_ids):
    if len(file_ids)>10: raise ValueError("A maximum of 10 files can be supplied to one execution.")
    return [read_file(x) for x in file_ids]
def _file_context_text(files):
    return "\n\n".join(f"FILE: {x.get('filename',x.get('file_id','unknown'))}\nTYPE: {x.get('extension','')}\nEXTRACTED CONTENT:\n{str(x.get('content',''))[:12000]}" for x in files)
def _run_worker(worker_id, task_type, prompt, files):
    if worker_id=="gemini": return generate_text(prompt)
    if worker_id=="claude": return generate_claude(prompt)
    if worker_id=="perplexity": return generate_perplexity(prompt)
    if worker_id in {"local-tools","local-validator"}: return execute_local_task(task_type,prompt,file_context=files)
    if worker_id.startswith("custom-"): return generate_custom(worker_id,prompt)
    raise RuntimeError(f"Worker '{worker_id}' has no registered executor.")
def execute_task(request: ExecutionRequest, *, free_only=True) -> ExecutionResponse:
    route=route_task(request.task_type,free_only=free_only,exclude_worker_ids=set(request.excluded_worker_ids))
    if request.forced_worker_id:
        candidate=next((x for x in route.candidates if x.worker_id==request.forced_worker_id and x.execution_ready and x.eligible_for_task),None)
        if candidate is None: raise RuntimeError(f"Manager selected worker '{request.forced_worker_id}', but that worker is not execution-ready, eligible, or allowed for this task.")
        policy="manager_directed_allocation"
    else:
        if not route.execution_ready or not route.recommended_worker_id: raise RuntimeError(f"No execution-ready free worker is available for task type '{request.task_type}'.")
        candidate=next((x for x in route.candidates if x.worker_id==route.recommended_worker_id and x.execution_ready and x.eligible_for_task),None)
        if candidate is None: raise RuntimeError(f"Worker routing selected '{route.recommended_worker_id}', but that worker is not execution-ready or eligible.")
        policy=route.routing_policy
    files=_load_files(request.file_ids); prompt=request.prompt+("\n\nUploaded file context:\n"+_file_context_text(files) if files else "")
    try: result=_run_worker(candidate.worker_id,request.task_type,prompt,files)
    except Exception: record_result(candidate.worker_id,task_type=request.task_type,success=False); raise
    telemetry=result["telemetry"]; record_result(candidate.worker_id,task_type=request.task_type,success=True,latency_ms=float(telemetry.get("last_latency_ms") or 0))
    return ExecutionResponse(status="completed",task_type=request.task_type,worker_id=candidate.worker_id,worker_name=candidate.name,routing_policy=policy,route_score=candidate.score,output=str(result["text"]),telemetry=telemetry)

def _task_prompt(objective,title,task_type,inputs,artifacts,feedback=None):
    context=""; supplied=[f"{name}: {artifacts[name]}" for name in inputs if name in artifacts] if inputs else []
    if supplied: context="\n\nPrevious task outputs:\n"+"\n\n".join(supplied)
    feedback_text=f"\n\nQA problem to fix:\n{feedback}" if feedback else ""; role=""
    if task_type=="quality_review": role="\n\nReview the upstream employee output independently for factual accuracy, completeness, relevance, structure, consistency, and compliance. Do not make the final acceptance decision. End exactly with: Quality score: <0-100>\nProblem identified: <specific problem or None identified.>\nRecommendation to NEXUS Manager: <PASS or REWORK>."
    return f"Mission objective:\n{objective}\n\nCurrent task: {title}\nTask type: {task_type}\nComplete only this task and produce a concise artifact for downstream employees.{role}{context}{feedback_text}"
def _artifact_type(task_type): return {"research":"research_brief","file_analysis":"file_analysis","data_analysis":"analysis_findings","presentation":"presentation_draft","quality_review":"quality_review","writing":"written_draft","image_generation":"image_output","coding":"code_output","general_reasoning":"reasoning_output"}.get(task_type,"task_output")
def _review_recommendation(output):
    m=re.search(r"Recommendation to NEXUS Manager:\s*(PASS|REWORK)",output,re.I)
    return m.group(1).upper() if m else next((x.strip().upper() for x in reversed(output.splitlines()) if x.strip().upper() in {"PASS","REWORK"}),None)
def _review_problem(output):
    m=re.search(r"Problem identified:\s*(.+)",output,re.I); return m.group(1).strip() if m else None
def _quality_score(output):
    m=re.search(r"Quality score:\s*(\d+(?:\.\d+)?)",output,re.I); return max(0,min(100,float(m.group(1)))) if m else None
def _mission_response(status,plan,execution_order,manager_decision,rework_count,records,artifacts): return MissionExecutionResponse(status=status,objective=plan.objective,execution_order=execution_order,manager_decision=manager_decision,rework_count=rework_count,max_reworks=3,tasks=records,artifacts=artifacts)

# Full mission engine retained; custom workers use the same Manager -> Execute -> QA -> Learning pipeline.
def execute_mission(request: MissionExecutionRequest, *, free_only=True, state_callback: Callable[[str,dict],None]|None=None) -> MissionExecutionResponse:
    analysis=analyze_prompt(request.prompt); plan=build_task_plan(analysis); artifacts_by_name={}; rework_feedback_by_task={}; artifact_records=[]; records=[]; execution_order=list(plan.execution_order); task_by_id={t.task_id:t for t in plan.tasks}; rework_count=0; resource_budget=request.resource_budget; resource_used=0.0; index=0
    if state_callback: state_callback("ALLOCATING",{"objective":plan.objective,"task_count":len(plan.tasks),"sprint":1})
    while index<len(execution_order):
        task=task_by_id[execution_order[index]]
        if state_callback: state_callback("REVIEWING" if task.task_type=="quality_review" else "EXECUTING",{"task_id":task.task_id,"task_type":task.task_type,"sprint":task.sprint})
        missing=[d for d in task.dependencies if not any(r.task_id==d and r.status in {"completed","reviewed"} for r in records)]
        if missing:
            records.append(TaskExecutionRecord(task_id=task.task_id,task_type=task.task_type,title=task.title,status="blocked",sprint=task.sprint,error=f"Dependencies not completed: {', '.join(missing)}")); break
        try:
            feedback=rework_feedback_by_task.get(task.task_id); is_review=task.task_type=="quality_review"; excluded={r.worker_id for r in records if r.worker_id} if is_review else set(); task_prompt=_task_prompt(plan.objective,task.title,task.task_type,task.inputs,artifacts_by_name,feedback); budget_remaining=int(max(0,resource_budget-resource_used)); allocation=decide_worker_for_task(task.task_type,prompt=task_prompt,free_only=free_only,budget_remaining=budget_remaining,exclude_worker_ids=excluded)
            if allocation.action=="STOP" or not allocation.selected_worker_id: raise RuntimeError(f"Manager stopped task '{task.title}': {allocation.rationale}")
            cost=allocation.resource_cost
            if resource_used+cost>resource_budget: raise RuntimeError(f"Resource budget exhausted for task '{task.title}'.")
            execution=execute_task(ExecutionRequest(task_type=task.task_type,prompt=task_prompt,file_ids=request.file_ids,forced_worker_id=allocation.selected_worker_id,excluded_worker_ids=list(excluded)),free_only=free_only); resource_used+=1
            collaborators=[]
            for collaborator_id in allocation.collaborator_worker_ids:
                if collaborator_id in excluded or collaborator_id==execution.worker_id: continue
                collab=execute_task(ExecutionRequest(task_type=task.task_type,prompt=task_prompt+"\n\nProvide an independent collaborating perspective.",file_ids=request.file_ids,forced_worker_id=collaborator_id,excluded_worker_ids=list(excluded)),free_only=free_only); resource_used+=1; collaborators.append(collab.output)
            combined=execution.output+("\n\n--- COLLABORATOR INPUT ---\n"+"\n\n".join(collaborators) if collaborators else ""); artifact_ids=[]
            for output_name in task.outputs:
                artifact_id=f"{task.task_id}:{output_name}"; artifact_records.append(ArtifactRecord(artifact_id=artifact_id,task_id=task.task_id,name=output_name,artifact_type=_artifact_type(task.task_type),content=combined,size_chars=len(combined),preview=combined[:280].replace("\n"," "))); artifacts_by_name[output_name]=combined; artifact_ids.append(artifact_id)
            base=dict(task_id=task.task_id,task_type=task.task_type,title=task.title,worker_id=execution.worker_id,worker_name=execution.worker_name,output=combined,route_score=execution.route_score,telemetry=execution.telemetry,artifact_ids=artifact_ids,collaborators=allocation.collaborator_worker_ids,candidate_worker_ids=allocation.candidate_worker_ids,manager_confidence=allocation.confidence,manager_estimated_value=allocation.estimated_value,manager_resource_cost=cost,manager_decision=allocation.action,manager_rationale=allocation.rationale,sprint=task.sprint)
            if task.quality_gate:
                recommendation=_review_recommendation(execution.output) or "REWORK"; problem=_review_problem(execution.output); qscore=_quality_score(execution.output); records.append(TaskExecutionRecord(status="reviewed",quality_decision=recommendation,quality_score=qscore,review_recommendation=recommendation,rework_number=rework_count,rework_problem=problem,**base)); record_result(execution.worker_id,task_type="quality_review",success=True,latency_ms=float(execution.telemetry.get("last_latency_ms") or 0),quality=recommendation)
                if recommendation=="REWORK":
                    if rework_count>=3: return _mission_response("rework_limit_reached",plan,execution_order,"REWORK",rework_count,records,artifact_records)
                    target=next((r for r in reversed(records[:-1]) if r.status=="completed" and r.task_type!="quality_review"),None)
                    if target is None: return _mission_response("rework_required",plan,execution_order,"REWORK",rework_count,records,artifact_records)
                    rework_count+=1; target_task=task_by_id[target.task_id]; rework_id=f"{target.task_id}_rework_{rework_count}"; rework_task=target_task.model_copy(update={"task_id":rework_id,"title":f"Rework #{rework_count}: {target.title}","dependencies":[task.task_id],"inputs":list(target_task.outputs),"quality_gate":False,"outputs":[f"{target.task_type}_rework_{rework_count}"],"sprint":task.sprint+1}); task_by_id[rework_id]=rework_task; rework_feedback_by_task[rework_id]=problem or "Correct the reviewed work."; execution_order.insert(index+1,rework_id); review_id=f"quality_review_{rework_count}"; review_task=task_by_id[task.task_id].model_copy(update={"task_id":review_id,"title":f"Review rework #{rework_count}","dependencies":[rework_id],"inputs":list(rework_task.outputs),"outputs":[f"quality_review_{rework_count}"],"quality_gate":True,"sprint":task.sprint+1}); task_by_id[review_id]=review_task; execution_order.insert(index+2,review_id)
            else:
                records.append(TaskExecutionRecord(status="completed",**base))
                if allocation.verification_required and not is_review:
                    review_id=f"manager_verify_{task.task_id}"; review_task=task.model_copy(update={"task_id":review_id,"title":f"Independent Manager verification: {task.title}","task_type":"quality_review","dependencies":[task.task_id],"inputs":list(task.outputs),"outputs":[f"manager_verification_{task.task_id}"],"quality_gate":True,"sprint":task.sprint}); task_by_id[review_id]=review_task; execution_order.insert(index+1,review_id)
        except Exception as exc:
            records.append(TaskExecutionRecord(task_id=task.task_id,task_type=task.task_type,title=task.title,status="failed",sprint=task.sprint,error=str(exc),manager_decision="STOP")); break
        index+=1
    successful=[r for r in records if r.status in {"completed","reviewed"}]; failed=[r for r in records if r.status in {"failed","blocked"}]; reviews=[r for r in records if r.task_type=="quality_review" and r.status=="reviewed"]; all_pass=bool(reviews) and all(r.quality_decision=="PASS" for r in reviews); accepted=bool(successful) and not failed and (all_pass or not reviews); decision="ACCEPT" if accepted else "REJECT"; status="completed" if accepted else ("rework_limit_reached" if rework_count>=3 else "failed")
    if state_callback: state_callback("MANAGER_REVIEW",{"manager_decision":decision,"rework_count":rework_count,"resource_used":resource_used,"resource_budget":resource_budget})
    return _mission_response(status,plan,execution_order,decision,rework_count,records,artifact_records)
