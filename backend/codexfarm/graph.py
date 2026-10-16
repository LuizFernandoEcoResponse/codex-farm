from __future__ import annotations
import concurrent.futures, os, threading
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from . import store
from .providers import CodexCLIProvider

MAX_AGENTS=3
_GLOBAL_AGENT_SLOTS=threading.BoundedSemaphore(MAX_AGENTS)

class MissionState(TypedDict, total=False):
    mission_id: str
    cwd: str
    autonomy: str
    goal: str
    tasks: list[dict]
    results: list[dict]
    status: str

provider=CodexCLIProvider()

def _worker(state: MissionState):
    mid=state["mission_id"]; results=[]
    if state["autonomy"]=="supervised":
        store.transition(mid,"awaiting_approval")
        store.event(mid,"approval.required","Supervised mode requires a human decision before agents run")
        return {"results":[],"status":"awaiting_approval"}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_AGENTS) as pool:
        future_map={pool.submit(_run_task,state,t):t for t in state["tasks"]}
        for fut in concurrent.futures.as_completed(future_map):
            task=future_map[fut]
            try: results.append({"task_id":task["id"],"result":fut.result(),"error":None})
            except Exception as exc: results.append({"task_id":task["id"],"result":None,"error":str(exc)[:3000]})
    return {"results":results}

def _run_task(state, task):
    mid=state["mission_id"]
    with _GLOBAL_AGENT_SLOTS:
        return _run_claimed_task(state,task)

def _run_claimed_task(state,task):
    mid=state["mission_id"]
    if not store.claim_task(task["id"]): return None
    prompt=("You are a CodexFarm research worker. Complete the assigned mission research using reliable sources. "
      "Return a concise report with claims, source title, URL, evidence, uncertainty and practical implications. "
      "Do not modify files, run external side effects, spend money, deploy, or claim that an unverified result is verified. "
      f"\nMission: {state['goal']}\nRole: {task['role']}\nAssignment: {task['prompt']}\n")
    try:
        result=provider.run(prompt,state["cwd"],state["autonomy"],mid)
        store.finish_task(task["id"],result=result)
        return result
    except Exception as exc:
        store.finish_task(task["id"],error=str(exc)[:3000]); raise

def _audit(state: MissionState):
    mid=state["mission_id"]
    mission=store.get_mission(mid)
    if not mission or mission["status"]=="cancelled": return {"status":"cancelled"}
    failed=[r for r in state.get("results",[]) if r.get("error")]
    if failed:
        store.transition(mid,"failed")
        store.event(mid,"audit.blocked",f"Audit not run: {len(failed)} agent task(s) failed")
        return {"status":"failed"}
    report="\n\n".join(f"## {r['task_id']}\n{r.get('result') or ''}" for r in state.get("results",[]))
    try:
        with _GLOBAL_AGENT_SLOTS:
            audit=provider.run("Audit the following research deliverables. Identify unsupported claims, missing/weak sources, contradictions, safety limitations, and whether the criteria are met. Do not invent research. Return a verdict and actionable gaps.\n\n"+report,state["cwd"],state["autonomy"],mid)
        store.event(mid,"audit.completed",audit[:5000])
        store.transition(mid,"completed")
        return {"status":"completed"}
    except Exception as exc:
        store.event(mid,"audit.failed",str(exc)[:3000]); store.transition(mid,"failed")
        return {"status":"failed"}

def build_graph():
    graph=StateGraph(MissionState)
    graph.add_node("execute",_worker)
    graph.add_node("audit",_audit)
    graph.add_edge(START,"execute")
    graph.add_conditional_edges("execute",lambda s: END if s.get("status")=="awaiting_approval" else "audit")
    graph.add_edge("audit",END)
    return graph

def run_mission(mid: str, root: str):
    mission=store.get_mission(mid)
    if not mission: return
    # Bound all Codex sessions to the configured project root.
    cwd=os.path.realpath(root); base=os.path.realpath(os.getenv("CODEXFARM_PROJECT_ROOT",root))
    if os.path.commonpath([base,cwd])!=base: raise RuntimeError("Project path escapes the configured root")
    tasks=mission["tasks"]
    if not store.start_mission(mid): return
    # Keep the durable checkpoint connection alive through invoke.
    saver=SqliteSaver.from_conn_string(str(store.DB_PATH.parent/"langgraph.sqlite3"))
    with saver as checkpointer:
        app=build_graph().compile(checkpointer=checkpointer)
        app.invoke({"mission_id":mid,"cwd":cwd,"autonomy":mission["autonomy"],"goal":mission["goal"],"tasks":tasks},config={"configurable":{"thread_id":mid}})
