# Root sdist Contamination Root Cause Report

- Work item: `TASK-042`
- Investigation status: `root_cause_found`
- Evidence: `../evidence/root-sdist-contamination-investigation.md`

The 0.4.39 root sdist is not a valid release artifact. The build wrapper temporarily moves the existing desktop bundle to a directory created inside the Hatch project root. Hatch includes that live temporary directory in the sdist, producing a 177 MiB archive with 2,186 unrelated desktop bundle entries. The temporary source directory is deleted after the build, which hid the contamination from normal workspace inspection.

Contracts 0.4.4 and SDK 0.4.5 artifacts are unaffected. Formal PyPI upload remains blocked pending confirmation of the root-cause fix boundary, root sdist rebuild, refreshed hash/evidence and independent re-review.
