# ADR 0001: Codex CLI workers with LangGraph orchestration

Status: accepted for MVP

## Context

CodexFarm needs resumable orchestration, concurrent specialist work and an execution provider whose actual installed interface can be verified. Codex CLI 0.159.2 is present in the cloud runtime and supports noninteractive JSONL execution with explicit sandbox modes. LangGraph Python provides graph orchestration and SQLite checkpoints.

## Decision

Use a FastAPI service, LangGraph StateGraph and SQLite for mission/task/event persistence and checkpoints. Launch three Codex CLI workers concurrently, then run a separate Codex auditor. Restrict workers to the configured project root. Keep provider adapters separate; OpenRouter remains unavailable until a tested adapter, credentials and real provider-side spend controls exist.

## Consequences

The MVP is single-host and SQLite-backed. A process restart requeues interrupted tasks; task outputs are persisted before audit. The CLI account's ChatGPT login does not establish API credits or a guaranteed US$10 limit. Usage/billing cannot be treated as metered or enforced until provider usage data and hard provider controls are implemented. The current dashboard reports this limitation.
