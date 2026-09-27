# ChatGPT / Codex integration

Use `../UNIVERSAL_AGENT_PROMPT.md` as the governing instructions.

Recommended behavior:

1. Run `aqg status` and `aqg next` before selecting work.
2. Use AQG lifecycle commands rather than manually changing governed fields.
3. Record real test/diff/log evidence with `aqg add-evidence` and map ACs with `aqg satisfy`.
4. Complete Verify before `aqg approve`; re-approve after any material change.
5. Require both `aqg validate --strict` and `aqg release-check`, plus the project's normal test suite, before reporting release readiness.
6. Do not modify `policy.toml` to bypass review or release blocking without explicit human authorization.
7. Respect the v0.1 single-writer limitation.
