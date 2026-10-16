from __future__ import annotations
import os, threading, shutil
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from . import store
from .graph import run_mission, MAX_AGENTS
from .providers import cancel_provider_runs

app=FastAPI(title="CodexFarm API",version="0.1.0")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:3000"],allow_methods=["*"],allow_headers=["*"])
store.init_db()
_root=os.path.realpath(os.getenv("CODEXFARM_PROJECT_ROOT",str(Path(__file__).resolve().parents[2])))
_workers: dict[str,threading.Thread]={}

class CreateMission(BaseModel):
    title: str=Field(min_length=3,max_length=120)
    goal: str=Field(min_length=20,max_length=12000)
    autonomy: str=Field(default="balanced",pattern="^(supervised|balanced|sandbox)$")
    budget_usd: float=Field(default=10.0,gt=0,le=10.0)

ROLES=[("Research analyst","Investigate the core technical and domain evidence; cite authoritative sources."),("Systems engineer","Investigate architecture, dependencies, cost and implementation tradeoffs."),("Risk and validation reviewer","Investigate failure modes, safety limits and measurable validation criteria; cross-check other likely assumptions independently.")]
def specs(goal): return [{"role":role,"prompt":f"{assignment}\nMission focus: {goal}"} for role,assignment in ROLES]

def launch(mid):
    def work():
        try: run_mission(mid,_root)
        except Exception as exc:
            store.transition(mid,"failed"); store.event(mid,"mission.error",str(exc)[:3000])
        finally: _workers.pop(mid,None)
    if mid not in _workers or not _workers[mid].is_alive():
        t=threading.Thread(target=work,daemon=True); _workers[mid]=t;t.start()

@app.on_event("startup")
def resume_queued_missions():
    for mid in store.recoverable_missions(): launch(mid)

@app.get("/api/health")
def health():
    return {"status":"ok","provider":"codex-cli","codex_available":shutil.which("codex") is not None,"autonomy_modes":["supervised","balanced","sandbox"],"max_parallel_agents":MAX_AGENTS,"budget_limit_usd":10,"budget_enforcement":"not_available_without_provider_usage_metering"}

@app.get("/api/missions")
def missions(): return store.list_missions()

@app.post("/api/missions",status_code=201)
def create(body: CreateMission):
    mid=store.create_mission(body.title.strip(),body.goal.strip(),body.autonomy,body.budget_usd,specs(body.goal))
    if body.autonomy=="supervised":
        # Hold the mission for explicit API approval.
        store.transition(mid,"awaiting_approval")
        store.event(mid,"approval.required","Supervised mode waits for explicit approval")
    else: launch(mid)
    return store.get_mission(mid)

@app.get("/api/missions/{mid}")
def mission(mid: str):
    item=store.get_mission(mid)
    if not item: raise HTTPException(404,"Mission not found")
    return item

@app.post("/api/missions/{mid}/approve")
def approve(mid: str):
    item=store.get_mission(mid)
    if not item: raise HTTPException(404,"Mission not found")
    if item["status"]!="awaiting_approval": raise HTTPException(409,"Mission is not awaiting approval")
    store.transition(mid,"queued"); launch(mid); return store.get_mission(mid)

@app.post("/api/missions/{mid}/cancel")
def cancel(mid: str):
    if not store.get_mission(mid): raise HTTPException(404,"Mission not found")
    cancel_provider_runs(mid); store.cancel(mid); return store.get_mission(mid)

@app.post("/api/missions/{mid}/retry")
def retry(mid: str):
    if not store.get_mission(mid): raise HTTPException(404,"Mission not found")
    store.retry(mid); launch(mid); return store.get_mission(mid)
