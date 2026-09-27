# Cursor integration

Use `../UNIVERSAL_AGENT_PROMPT.md` as the governing instructions.

Prefer AQG lifecycle commands over directly editing governed status/check boxes. Run `aqg status`, `aqg next`, and the repository's real tests throughout the task. Approval must follow Verify. Before final completion run both `aqg validate --strict` and `aqg release-check`. Do not weaken `policy.toml` to create a green result.
