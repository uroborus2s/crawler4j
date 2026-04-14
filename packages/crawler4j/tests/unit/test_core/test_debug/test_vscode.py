import json

from src.core.debug.vscode import ensure_vscode_attach_config


def test_ensure_vscode_attach_config_creates_launch_json(tmp_path):
    module_dir = tmp_path / "demo_module"
    module_dir.mkdir()

    launch_path = ensure_vscode_attach_config(module_dir, host="127.0.0.1", port=5678)

    assert launch_path == module_dir / ".vscode" / "launch.json"
    payload = json.loads(launch_path.read_text(encoding="utf-8"))
    assert payload["version"] == "0.2.0"
    assert payload["configurations"][0]["name"] == "Attach to Crawler4j"
    assert payload["configurations"][0]["connect"] == {"host": "127.0.0.1", "port": 5678}


def test_ensure_vscode_attach_config_updates_existing_configuration(tmp_path):
    module_dir = tmp_path / "demo_module"
    vscode_dir = module_dir / ".vscode"
    vscode_dir.mkdir(parents=True)
    launch_path = vscode_dir / "launch.json"
    launch_path.write_text(
        json.dumps(
            {
                "version": "0.2.0",
                "configurations": [
                    {
                        "name": "Keep Me",
                        "type": "debugpy",
                        "request": "attach",
                        "connect": {"host": "127.0.0.1", "port": 9999},
                    },
                    {
                        "name": "Attach to Crawler4j",
                        "type": "debugpy",
                        "request": "attach",
                        "connect": {"host": "127.0.0.1", "port": 1111},
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    ensure_vscode_attach_config(module_dir, host="127.0.0.1", port=5679)

    payload = json.loads(launch_path.read_text(encoding="utf-8"))
    assert len(payload["configurations"]) == 2
    attach_config = next(item for item in payload["configurations"] if item["name"] == "Attach to Crawler4j")
    assert attach_config["connect"]["port"] == 5679
    keep_config = next(item for item in payload["configurations"] if item["name"] == "Keep Me")
    assert keep_config["connect"]["port"] == 9999
