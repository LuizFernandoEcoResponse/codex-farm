# CodexFarm

A single-host research preview for mission orchestration with three real Codex CLI workers, parallel execution, SQLite persistence and a separate Codex auditor. The dashboard is Next.js/TypeScript; orchestration is FastAPI + LangGraph.

## Requirements

- Python 3.12 and `pip`
- Node.js 20+ and npm
- Codex CLI installed and authenticated in the runtime. ChatGPT sign-in does not grant API credits or a guaranteed spend cap.

## Install

From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install --requirement backend/requirements.lock
(cd web && npm ci)
```


## Run

Terminal 1: `CODEXFARM_PROJECT_ROOT="$PWD" .venv/bin/uvicorn codexfarm.api:app --app-dir backend --host 0.0.0.0 --port 8000`

Terminal 2: `cd web && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev`

Open the dashboard locally at `http://localhost:3000`. The API health endpoint is `/api/health`; interactive API documentation is `/docs`.

## Scope and limits

Create a mission in balanced mode to run three specialist Codex CLI sessions in parallel, persist each result, and run an independent source/claim audit. SQLite stores missions, tasks, events and LangGraph checkpoints. Cancel, retry and supervised approval endpoints are available. The supervised mode waits for approval; balanced and sandbox modes currently use the same Codex workspace-write sandbox and therefore are not distinct security profiles yet. Task prompts forbid file modifications and external side effects; do not treat prompts as a security boundary.

The configured US$10 value is a display/input ceiling only. Codex CLI does not expose a provider-enforced US$10 cap here. Do not run paid API workloads on the assumption that this budget is enforced. OpenRouter is an interface placeholder and is not enabled. Multi-user auth, per-project OS isolation, model/usage metering, provider hard limits, cross-host persistence and deployment are not implemented.

## Checks

Backend: `PYTHONPATH=backend python -m unittest discover -s tests -v`
Frontend: `(cd web && npm run build)`

See `docs/research.md` and `docs/adr/0001-runtime-and-orchestration.md` for the initial architecture decision. The Clodfarm MIT license and architecture were reviewed as reference patterns; no Clodfarm source was copied into this repository.
