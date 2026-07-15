# Independent Release Candidate Review Task

You are an independent reviewer. Do not rely on the implementer's conversation history; inspect only the file package and current workspace diff/artifacts.

## Inputs

- Work item: `TASK-042`
- Review type: task-level Spec + Quality Review before irreversible PyPI upload
- Requirements: `.factory/workitems/TASK-042/task-briefs/release-candidate.md`
- Plan: `.factory/workitems/implementation/TASK-042-release-cr022-packages-and-client.md`
- Implementer report: `.factory/workitems/TASK-042/reports/release-candidate-implementer-report.md`
- Verification evidence: `.factory/workitems/TASK-042/evidence/release.md`
- Ledger: `.factory/workitems/TASK-042/ledger.jsonl`
- Diff package: current `git diff`, untracked TASK-042 files, and built distributions under `dist/`
- Architecture boundary: existing Contracts/SDK PyPI projects only; root package build only; no consumer module, desktop installer, tag or GitHub Release

## Job

1. Verify version/dependency consistency and that the intended public API release is covered.
2. Verify artifact names, metadata, hashes and dry-run evidence independently where practical.
3. Verify the known 13 full-unit failures are clearly separated and no changed-scope failure is hidden.
4. Verify release docs/memory and no overbroad distribution action.
5. Record reviewer independence metadata and score using the project rubric.
6. Write the result to `.factory/workitems/TASK-042/reviews/release-candidate-independent-review.md`.
7. Do not upload packages, commit, push, or mark the work item done.
