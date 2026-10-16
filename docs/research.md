# Initial technical research

Research performed 2026-10-16 against the configured runtime and upstream repositories.

## Clodfarm

The referenced `matank001/clodfarm` checkout is MIT licensed (copyright Duke Security, Inc., 2026). Preserve its notice if any source is reused. This MVP does not copy Clodfarm source. Its useful design patterns are an abstract state store, atomic claims with leases, retries and stale-worker recovery, durable process supervision, audit events, policy gates, and isolated task worktrees. Its runner/UI are coupled to Claude Code; adapt lifecycle contracts behind provider abstractions instead. References: [license](https://github.com/matank001/clodfarm/blob/25036daa30af643dbdc56f74bcd30c031d891145/LICENSE), [architecture](https://github.com/matank001/clodfarm/blob/25036daa30af643dbdc56f74bcd30c031d891145/docs/architecture.md), [store](https://github.com/matank001/clodfarm/blob/25036daa30af643dbdc56f74bcd30c031d891145/clodfarm/store.py), [backend](https://github.com/matank001/clodfarm/blob/25036daa30af643dbdc56f74bcd30c031d891145/clodfarm/backends.py).

## Codex

The environment has Codex CLI 0.159.2 and `codex login status` reports a ChatGPT login. Its non-interactive JSONL interface and sandbox options are used by the provider adapter. A read-only execution check did not reach the model: the CLI failed to initialize its in-process App Server because the runtime filesystem is read-only. Thus Codex worker execution is implemented but has not been verified in this machine. ChatGPT sign-in does not establish API credits or a guaranteed US$10 limit.

The official TypeScript SDK is `@openai/codex-sdk`; it wraps the CLI, supports streamed events, thread resume and usage reporting. The App Server is an experimental stdio/JSON-RPC surface. These remain migration options; the MVP currently calls the CLI directly from Python. References: [Codex SDK](https://github.com/openai/codex/tree/main/sdk/typescript), [Codex source and CLI](https://github.com/openai/codex).

## LangGraph

LangGraph's StateGraph is used for the worker and audit stages; its SQLite checkpointer persists graph state, while application SQLite tables hold mission, task and event data. The MVP is a single-host design. References: [LangGraph](https://github.com/langchain-ai/langgraph), [LangGraph.js](https://github.com/langchain-ai/langgraphjs).

## REA

The mission's “REA” reference has not been identified or verified. The `anthropics/skills` repository is not assumed to be REA. Resolve the intended project before integration.
