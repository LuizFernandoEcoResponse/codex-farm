from __future__ import annotations
import os, shutil, subprocess, threading

_active_lock = threading.Lock()
_active: dict[str, set[subprocess.Popen]] = {}

def cancel_provider_runs(mission_id: str):
    with _active_lock:
        processes=list(_active.get(mission_id,set()))
    for process in processes:
        if process.poll() is None:
            process.terminate()

class CodexCLIProvider:
    """Run the installed Codex CLI using its existing local authentication."""
    name="codex-cli"
    def __init__(self, timeout_seconds=1200): self.timeout_seconds=timeout_seconds
    def available(self): return shutil.which("codex") is not None
    def run(self, prompt: str, cwd: str, autonomy: str, mission_id: str|None=None) -> str:
        binary=shutil.which("codex")
        if not binary: raise RuntimeError("Codex CLI was not found on PATH")
        sandbox="read-only" if autonomy=="supervised" else "workspace-write"
        # Prompts are data; no shell is involved, and all writes are confined by Codex's sandbox.
        p=subprocess.Popen([binary,"exec","--json","--ephemeral","--sandbox",sandbox,"-C",cwd,prompt],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        if mission_id:
            with _active_lock: _active.setdefault(mission_id,set()).add(p)
        try:
            stdout,stderr=p.communicate(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            p.kill(); stdout,stderr=p.communicate(); raise RuntimeError("Codex execution timed out")
        finally:
            if mission_id:
                with _active_lock:
                    _active.get(mission_id,set()).discard(p)
                    if not _active.get(mission_id): _active.pop(mission_id,None)
        if p.returncode: raise RuntimeError((stderr or stdout)[-4000:] or f"Codex exited {p.returncode}")
        outputs=[]
        for line in stdout.splitlines():
            try:
                import json
                obj=json.loads(line)
                if obj.get("type")=="item.completed" and obj.get("item",{}).get("type")=="agent_message": outputs.append(obj["item"].get("text",""))
                elif obj.get("type")=="turn.completed" and not outputs: outputs.append(obj.get("result",""))
            except (ValueError, TypeError): pass
        return "\n".join(x for x in outputs if x).strip() or p.stdout[-12000:]

class OpenRouterProvider:
    """Placeholder interface: unavailable until API credentials and verified costs are configured."""
    name="openrouter"
    def available(self): return bool(os.getenv("OPENROUTER_API_KEY"))
    def run(self,*args,**kwargs): raise RuntimeError("OpenRouter adapter is not implemented; no provider calls were made")
