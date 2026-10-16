# ADR 0002: Do not claim a dollar budget without provider enforcement

Status: accepted for MVP

The mission starts with a requested US$10 budget. The available Codex CLI login does not expose a provider-enforced dollar limit here. Codex usage pricing/credits cannot be inferred from ChatGPT sign-in. The API accepts a displayed ceiling up to US$10, but it does not meter spend, stop calls by cost, or guarantee that cap. The health endpoint and UI disclose this. OpenRouter remains disabled until a real adapter, credentials, verified costs and provider-side budget controls are available.

Supervised missions require explicit approval. Balanced and sandbox currently map to Codex `workspace-write`; sandbox is not yet a separate hardened isolation profile. Prompts prohibit file changes and external actions for the research workers, but prompts are not a security boundary. This deployment is single-user and has no authentication. Do not expose it to an untrusted network.
