# Claude Code integration

Use `../UNIVERSAL_AGENT_PROMPT.md` as the governing instructions.

During Test and Re-test, run the repository's actual tests and store sanitized objective evidence. Use `aqg add-evidence`, `aqg satisfy`, and `aqg validate --strict` instead of narrative completion statements. Complete Verify before final-state approval, then run `aqg release-check` before claiming release readiness. Do not change repository policy without explicit owner authorization. v0.1 assumes one AQG writer at a time.
