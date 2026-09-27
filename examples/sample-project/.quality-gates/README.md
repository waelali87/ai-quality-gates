# AI Quality Gates Workspace

Gate records live in `gates/`; policy lives in `policy.toml`.

Recommended flow: `aqg new` → edit DRAFT → `aqg start` → `aqg advance` → `aqg add-evidence` / `aqg satisfy` → `aqg verify` → `aqg approve` → `aqg close`.

Use `aqg validate --strict` for record integrity and `aqg release-check` for release readiness.

AQG v0.1 uses a single-writer model: do not run concurrent AQG mutations against the same workspace.
