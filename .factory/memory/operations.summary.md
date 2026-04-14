# Operations Summary

Recommended commands:

```bash
uv sync --all-packages
uv run pytest -q
uv run python -m src.ui.app
uv run python scripts/smoke_test_ui.py
```

Workspace root no longer relies on `uv run start`; the supported launch path is `uv run python -m src.ui.app`.
