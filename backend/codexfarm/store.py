from __future__ import annotations
import json, sqlite3, threading, time, uuid
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "codexfarm.sqlite3"
_lock = threading.RLock()

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db

def init_db():
    with _lock, connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY, title TEXT NOT NULL, goal TEXT NOT NULL, autonomy TEXT NOT NULL, budget_usd REAL NOT NULL, status TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE, role TEXT NOT NULL, prompt TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, lease_until REAL, result TEXT, error TEXT, started_at REAL, finished_at REAL);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE, task_id TEXT, kind TEXT NOT NULL, message TEXT NOT NULL, created_at REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS task_mission_idx ON tasks(mission_id);
        CREATE INDEX IF NOT EXISTS event_mission_idx ON events(mission_id,id);
        """)
        # Interrupted workers are retried after restart; completed rows remain untouched.
        now=time.time()
        db.execute("UPDATE tasks SET status='queued', lease_until=NULL WHERE status='running'")
        db.execute("UPDATE missions SET status='queued', updated_at=? WHERE status='running' AND NOT EXISTS (SELECT 1 FROM tasks WHERE tasks.mission_id=missions.id AND tasks.status='running')", (now,))

def event(mission_id: str, kind: str, message: str, task_id: str|None=None):
    with _lock, connect() as db:
        db.execute("INSERT INTO events(mission_id,task_id,kind,message,created_at) VALUES(?,?,?,?,?)", (mission_id,task_id,kind,message,time.time()))

def create_mission(title: str, goal: str, autonomy: str, budget: float, task_specs: list[dict[str,str]]):
    mid=str(uuid.uuid4()); now=time.time()
    with _lock, connect() as db:
        db.execute("INSERT INTO missions VALUES(?,?,?,?,?,?,?,?)", (mid,title,goal,autonomy,budget,"queued",now,now))
        for item in task_specs:
            db.execute("INSERT INTO tasks(id,mission_id,role,prompt,status) VALUES(?,?,?,?,?)", (str(uuid.uuid4()),mid,item["role"],item["prompt"],"queued"))
        db.execute("INSERT INTO events(mission_id,kind,message,created_at) VALUES(?,?,?,?)", (mid,"mission.created","Mission queued",now))
    return mid

def get_mission(mid: str):
    with connect() as db:
        m=db.execute("SELECT * FROM missions WHERE id=?",(mid,)).fetchone()
        if not m: return None
        return dict(m) | {"tasks":[dict(x) for x in db.execute("SELECT * FROM tasks WHERE mission_id=? ORDER BY rowid",(mid,))], "events":[dict(x) for x in db.execute("SELECT * FROM events WHERE mission_id=? ORDER BY id",(mid,))]}

def list_missions():
    with connect() as db: ids=[x[0] for x in db.execute("SELECT id FROM missions ORDER BY created_at DESC")]
    return [get_mission(x) for x in ids]

def transition(mid: str, status: str):
    with _lock, connect() as db: db.execute("UPDATE missions SET status=?,updated_at=? WHERE id=?",(status,time.time(),mid))

def start_mission(mid: str) -> bool:
    with _lock, connect() as db:
        cur=db.execute("UPDATE missions SET status='running',updated_at=? WHERE id=? AND status='queued'",(time.time(),mid))
        return cur.rowcount==1

def claim_task(tid: str, lease_seconds=1800):
    now=time.time()
    with _lock, connect() as db:
        cur=db.execute("UPDATE tasks SET status='running', attempts=attempts+1, started_at=?,lease_until=?,error=NULL WHERE id=? AND status IN ('queued','failed')",(now,now+lease_seconds,tid))
        return cur.rowcount==1

def finish_task(tid: str, result: str|None=None, error: str|None=None):
    status="completed" if error is None else "failed"
    with _lock, connect() as db:
        row=db.execute("SELECT mission_id FROM tasks WHERE id=?",(tid,)).fetchone()
        db.execute("UPDATE tasks SET status=?,result=?,error=?,finished_at=?,lease_until=NULL WHERE id=? AND status='running'",(status,result,error,time.time(),tid))
    if row: event(row[0],f"task.{status}",error or "Agent finished",tid)

def cancel(mid: str):
    with _lock, connect() as db:
        db.execute("UPDATE missions SET status='cancelled',updated_at=? WHERE id=? AND status IN ('queued','running','failed')",(time.time(),mid))
        db.execute("UPDATE tasks SET status='cancelled',lease_until=NULL WHERE mission_id=? AND status IN ('queued','running')",(mid,))
    event(mid,"mission.cancelled","Mission cancelled")

def retry(mid: str):
    with _lock, connect() as db:
        db.execute("UPDATE tasks SET status='queued',error=NULL WHERE mission_id=? AND status IN ('failed','cancelled')",(mid,))
        db.execute("UPDATE missions SET status='queued',updated_at=? WHERE id=? AND status IN ('failed','cancelled')",(time.time(),mid))
    event(mid,"mission.retried","Failed tasks queued for retry")


def recoverable_missions():
    with connect() as db:
        return [r[0] for r in db.execute("SELECT id FROM missions WHERE status='queued'")]
