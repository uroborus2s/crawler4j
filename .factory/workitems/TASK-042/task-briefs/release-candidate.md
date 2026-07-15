# TASK-042 Release Candidate Brief

## Scope

- Upgrade `crawler4j-contracts` from 0.4.3 to 0.4.4.
- Upgrade `crawler4j-sdk` from 0.4.4 to 0.4.5 and require `crawler4j-contracts>=0.4.4,<0.5.0`.
- Upgrade root/client `crawler4j` from 0.4.38 to 0.4.39 and use the same Contracts lower bound.
- Build all three Python distributions.
- Publish only Contracts and SDK to their existing PyPI projects, in that order.
- Do not create a new `crawler4j` PyPI project, desktop installers, tags, or GitHub Releases.
- After online verification, push all local commits on branch `0.4.0` to `origin/0.4.0`.

## Acceptance

- Version facts, README, dependency bounds and `uv.lock` agree.
- Target PyPI versions are unoccupied before upload.
- wheel/sdist metadata and SHA256 are recorded.
- Tests and static gates are proportionate to the public Contracts/SDK release.
- Contracts is online with matching hashes before SDK upload.
- SDK online metadata requires Contracts 0.4.4 and isolated PyPI installation succeeds.
- Release evidence distinguishes the 13 known sandbox/read-only database baseline failures from changed-scope results.

## Authority

The user explicitly requested version upgrades for required client/packages, publication of the latest packages to PyPI, and pushing all changes to the remote. This does not authorize creating additional distribution channels outside the established package projects and branch.
