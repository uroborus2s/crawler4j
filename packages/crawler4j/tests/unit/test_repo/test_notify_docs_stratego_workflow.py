from pathlib import Path

import yaml


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    target = Path(".github/workflows/notify-docs-stratego.yml")
    for parent in current.parents:
        if (parent / target).exists():
            return parent
    raise AssertionError("Could not locate repository root for notify-docs-stratego workflow test.")


def _load_workflow() -> dict:
    workflow_path = _repo_root() / ".github/workflows/notify-docs-stratego.yml"
    return yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_notify_docs_stratego_workflow_only_autonotifies_main_docs_changes() -> None:
    workflow = _load_workflow()
    push = workflow["on"]["push"]

    assert push["branches"] == ["main"]
    assert push["paths"] == ["docs/**"]


def test_notify_docs_stratego_dispatch_trims_secret_newlines_and_fails_on_http_errors() -> None:
    workflow = _load_workflow()
    notify_job = workflow["jobs"]["notify"]
    dispatch_step = next(
        step
        for step in notify_job["steps"]
        if step["name"] == "Send Repository Dispatch to docs-stratego"
    )
    run_script = dispatch_step["run"]

    assert "tr -d '\\r\\n'" in run_script
    assert "--fail-with-body" in run_script
