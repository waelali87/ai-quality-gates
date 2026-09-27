# Contributing

Contributions are welcome when they preserve AQG's core goals: deterministic records, evidence-backed closure, explicit policy, and low runtime complexity.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q src
```

## Required quality bar

Changes to parsing, lifecycle, policy, evidence, or approval semantics must include adversarial tests, not only happy-path tests. In particular, test whether the change can produce a false green result.

Before a pull request is considered ready:

```bash
aqg validate --strict examples/sample-project
aqg release-check examples/sample-project
```

## Design constraints

- Keep Markdown as the human-readable source format unless there is strong evidence to change it.
- Prefer standard-library solutions in v0.x.
- Do not conflate structural validation with release readiness.
- Do not weaken mandatory review/release policy merely to make tests pass.
- Preserve the explicit trust boundary.
- v0.1 is single-writer; do not claim multi-writer safety without implementing and testing locking.
