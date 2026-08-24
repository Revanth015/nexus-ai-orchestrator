from threading import RLock
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .config import settings
from .execution import ExecutionRequest, ExecutionResponse, MissionExecutionRequest, MissionExecutionResponse, execute_task, decide_worker_for_task, ManagerExecutionDecision
from .mission_execution_service import execute_mission_with_memory
from .file_store import save_upload
from .gemini_connector import GeminiStatus, GeminiTestRequest, status as gemini_status, test_connection
from .ai_connectors import claude_status, perplexity_status, test_claude, test_perplexity
from .ai_connections import list_connections, register_connection, delete_connection, test_connection as test_custom_connection, diagnose_connection
from .planner_models import PlanResponse
from .prompt_analyzer import analyze_prompt
from .prompt_models import PromptAnalysisResponse, PromptRequest
from .task_planner import build_task_plan
from . import worker_learning as _worker_learning
from .worker_learning import learning_snapshot, self_initialize, run_self_initialization
from .worker_registry import list_workers
from .worker_router import WorkerRouteResponse, route_task
from .collaboration_planner import CollaborationDecision, collaboration_history, plan_collaboration
from .adaptive_manager import AdaptiveMissionState, classify_replan_signal
from .audit_log import list_events, mission_summary
from .mission_memory import create_mission, get_mission, update_mission, transition, recent_memory, memory_snapshot
_worker_learning._LOCK=RLock()
app=FastAPI(title=settings.app_name,version="0.1.0",description="Free-first AI orchestration backend for NEXUS.")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
class AIConnectionRequest(BaseModel):
    name:str=Field(min_length=1,max_length=80); provider:str=Field(min_length=1,max_length=40); api_key:str=Field(min_length=1); model:str=Field(min_length=1,max_length=120); base_url:str=Field(min_length=1,max_length=300); free_verified:bool=False; capabilities:dict[str,float]=Field(default_factory=dict)
@app.get("/health")
def health(): return {"status":"ok","service":settings.app_name,"free_only":settings.free_only,"background_execution":settings.background_execution}
@app.post("/analyze",response_model=PromptAnalysisResponse)
def analyze(request:PromptRequest): return PromptAnalysisResponse(prompt=request.prompt,analysis=analyze_prompt(request.prompt))
@app.post("/plan",response_model=PlanResponse)
def plan(request:PromptRequest): return PlanResponse(plan=build_task_plan(analyze_prompt(request.prompt)))
@app.post("/files/upload")
async def upload_file(file:UploadFile=File(...)):
    try:return {"status":"uploaded","file":save_upload(file.filename or "uploaded_file",await file.read())}
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
    except Exception as exc:raise HTTPException(status_code=500,detail=f"File upload failed: {exc}") from exc
@app.get("/workers")
def workers():return {"free_only":settings.free_only,"workers":[w.model_dump(mode="json") for w in list_workers()],"note":"Routing scores are dynamic priors: live readiness plus observed task-specific performance update allocation over time."}
@app.get("/workers/connections")
def worker_connections():return {"connections":list_connections()}
@app.post("/workers/connections")
def add_worker_connection(request:AIConnectionRequest):
    try:return {"status":"registered","worker":register_connection(name=request.name,provider=request.provider,api_key=request.api_key,model=request.model,base_url=request.base_url,free_verified=request.free_verified,capabilities=request.capabilities)}
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
@app.delete("/workers/connections/{worker_id}")
def remove_worker_connection(worker_id:str):
    if not delete_connection(worker_id):raise HTTPException(status_code=404,detail="Custom AI employee not found")
    return {"status":"removed","worker_id":worker_id}
@app.post("/workers/connections/{worker_id}/test")
def test_worker_connection(worker_id:str):
    try:return test_custom_connection(worker_id)
    except ValueError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except Exception as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
@app.post("/workers/connections/{worker_id}/diagnose")
def diagnose_worker_connection(worker_id:str):
    try:return diagnose_connection(worker_id)
    except ValueError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except Exception as exc:raise HTTPException(status_code=502,detail={"message":str(exc)}) from exc
@app.get("/workers/learning")
def workers_learning():return learning_snapshot()
@app.get("/workers/collaboration")
def workers_collaboration():return collaboration_history()
@app.post("/workers/self-initialize")
def workers_self_initialize():return self_initialize()
@app.post("/workers/self-initialize/run")
def workers_self_initialize_run():
    try:return run_self_initialization()
    except Exception as exc:raise HTTPException(status_code=502,detail=f"Worker self-initialization failed: {exc}") from exc
@app.get("/route/{task_type}",response_model=WorkerRouteResponse)
def route(task_type:str)->WorkerRouteResponse:return route_task(task_type,free_only=settings.free_only)
@app.post("/manager/decide/{task_type}",response_model=ManagerExecutionDecision)
def manager_decide_endpoint(task_type:str,request:PromptRequest)->ManagerExecutionDecision:return decide_worker_for_task(task_type,prompt=request.prompt,free_only=settings.free_only)
@app.post("/missions")
def missions_create(request:PromptRequest):return {"status":"created","mission":create_mission(request.prompt)}
@app.get("/missions/{mission_id}")
def missions_get(mission_id:str):
    mission=get_mission(mission_id)
    if not mission:raise HTTPException(status_code=404,detail="Mission not found")
    return mission
@app.patch("/missions/{mission_id}")
def missions_update(mission_id:str,changes:dict[str,object]):
    try:return update_mission(mission_id,**changes)
    except KeyError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
@app.post("/missions/{mission_id}/transition")
def missions_transition(mission_id:str,request:dict[str,object]):
    try:return transition(mission_id,str(request.get("state","PLANNING")),reason=str(request.get("reason")) if request.get("reason") else None)
    except KeyError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
@app.get("/missions/{mission_id}/memory")
def missions_memory(mission_id:str):
    mission=get_mission(mission_id)
    if not mission:raise HTTPException(status_code=404,detail="Mission not found")
    return {"mission":mission,"audit":mission_summary(mission_id)}
@app.get("/corporate-memory")
def corporate_memory(keyword:str|None=None,limit:int=20):return {"missions":recent_memory(objective_keyword=keyword,limit=limit)}
@app.get("/corporate-memory/snapshot")
def corporate_memory_snapshot():return memory_snapshot()
@app.get("/audit/events")
def audit_events(mission_id:str|None=None,task_id:str|None=None,limit:int=100):return {"events":list_events(mission_id=mission_id,task_id=task_id,limit=limit)}
@app.get("/audit/missions/{mission_id}")
def audit_mission(mission_id:str):return mission_summary(mission_id)
@app.post("/collaboration/plan",response_model=CollaborationDecision)
def collaboration_plan(request:PromptRequest)->CollaborationDecision:
    analysis=analyze_prompt(request.prompt);task_type=analysis.task_types[0] if analysis.task_types else "general_reasoning";return plan_collaboration(task_type,request.prompt,free_only=settings.free_only)
@app.post("/adaptive/replan")
def adaptive_replan(request:PromptRequest):
    state=AdaptiveMissionState(objective=request.prompt);signal=classify_replan_signal(status="failed");decision=state.replan_decision(signal["trigger"],"unknown",signal["detail"]);return {"status":"replan_ready","decision":decision,"state":state.snapshot()}
@app.post("/adaptive/observe")
def adaptive_observe(request:dict[str,object]):
    objective=str(request.get("objective","Adaptive NEXUS mission"));state=AdaptiveMissionState(objective=objective);task_id=str(request.get("task_id","unknown"));status=str(request.get("status","completed"));missing=[str(x) for x in request.get("missing_inputs",[])] if isinstance(request.get("missing_inputs",[]),list) else [];recommendation=request.get("qa_recommendation");problem=request.get("qa_problem")
    if recommendation in {"PASS","REWORK"}:decision=state.observe_qa(task_id,str(recommendation),str(problem) if problem else None)
    elif missing:decision=state.observe_missing_input(task_id,", ".join(missing))
    elif status=="failed":decision=state.observe_failure(task_id,str(request.get("error","Task execution failed.")))
    else:decision={"action":"continue","replan":False,"reason":"No replanning signal detected."}
    return {"status":"observed","decision":decision,"state":state.snapshot()}
@app.post("/execute",response_model=ExecutionResponse)
def execute(request:ExecutionRequest)->ExecutionResponse:
    try:return execute_task(request,free_only=settings.free_only)
    except FileNotFoundError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except Exception as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
@app.post("/execute-mission",response_model=MissionExecutionResponse)
def execute_mission_endpoint(request:MissionExecutionRequest)->MissionExecutionResponse:
    try:return execute_mission_with_memory(request,free_only=settings.free_only)
    except FileNotFoundError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except Exception as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
@app.get("/connectors/gemini/status",response_model=GeminiStatus)
def gemini_connector_status()->GeminiStatus:return gemini_status()
@app.post("/connectors/gemini/test")
def gemini_connector_test(request:GeminiTestRequest):
    try:return {"status":"ok","result":test_connection(request.prompt)}
    except Exception as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
@app.get("/connectors/claude/status")
def claude_connector_status():return claude_status()
@app.post("/connectors/claude/test")
def claude_connector_test(request:GeminiTestRequest):
    try:return {"status":"ok","result":test_claude(request.prompt)}
    except Exception as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
@app.get("/connectors/perplexity/status")
def perplexity_connector_status():return perplexity_status()
@app.post("/connectors/perplexity/test")
def perplexity_connector_test(request:GeminiTestRequest):
    try:return {"status":"ok","result":test_perplexity(request.prompt)}
    except Exception as exc:raise HTTPException(status_code=502,detail=str(exc)) from exc
