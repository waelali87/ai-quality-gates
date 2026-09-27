# Findings-to-Gates Conversion Checklist

1. Collect all findings, recommendations, defects, risks, and missing requirements.
2. Deduplicate overlapping items.
3. Assign severity: Critical, High, Medium, Low.
4. Identify hard dependencies.
5. Create one action-oriented DRAFT gate per independently verifiable outcome.
6. Define a concrete Problem statement.
7. Define objective `AC-*` acceptance criteria.
8. Define required `EVID-*` evidence before execution.
9. Respect repository policy for mandatory review; do not downgrade policy to simplify execution.
10. Start only READY gates.
11. Execute sequentially: Analyze → Prepare → Execute → Test → Review → Fix → Re-test → Verify.
12. Record objective evidence and map each AC to PASS evidence.
13. Approve the final verified state only after Verify when review is required.
14. Re-approve after any material post-approval mutation.
15. Close only through `aqg close` after all closure preconditions pass.
16. Run `aqg validate --strict` for record integrity.
17. Run `aqg release-check` for release readiness.
18. Report unresolved or policy-blocking gates explicitly.
