# OpenCode integration

Use `../UNIVERSAL_AGENT_PROMPT.md` as the governing instructions.

Use `aqg next` to avoid severity-only scheduling that ignores prerequisites. Require structured evidence, verification mappings, and post-Verify approval when policy requires it. Before reporting completion run both `aqg validate --strict` and `aqg release-check`. Treat policy as owner-controlled and the v0.1 workspace as single-writer.
