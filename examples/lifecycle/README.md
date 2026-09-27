# Lifecycle Scenarios

The canonical executable example is [`../sample-project`](../sample-project).

It demonstrates:

- `GATE-001`: a Critical CLOSED gate with PASS file evidence, verification mapping, Verify-stage completion, fresh independent approval, and formal closure;
- `GATE-002`: a Medium READY DRAFT gate whose prerequisite is already CLOSED;
- default policy: Critical/High are release-blocking and require review; Medium does not block release while still DRAFT.

Check both layers:

```bash
aqg validate --strict examples/sample-project
aqg release-check examples/sample-project
```

Exception states:

```bash
aqg defer GATE-002 --reason "Waiting for external system" --by "Project Owner"
aqg waive GATE-002 --reason "Risk accepted" --by "Authorized Owner"
aqg resume GATE-002 --note "External dependency is available"
```

DEFERRED and WAIVED do not satisfy CLOSED dependencies. Under the default policy, a Critical/High exception also remains release-blocking.
