## Summary

Describe the change and the governance problem it solves.

## Validation

- [ ] `python -m unittest discover -s tests -v` passes.
- [ ] `python -m compileall -q src` passes.
- [ ] `aqg validate --strict examples/sample-project` passes.
- [ ] `aqg release-check examples/sample-project` passes.
- [ ] Documentation and CLI examples match behavior.
- [ ] No secrets or sensitive evidence were introduced.
- [ ] If gate schema/policy behavior changed, adversarial tests were added.
