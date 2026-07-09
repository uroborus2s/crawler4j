from types import SimpleNamespace
from unittest.mock import AsyncMock


def test_edit_env_dialog_allows_selecting_ip_when_env_has_no_proxy(qtbot, monkeypatch):
    import src.core.rem.ip_pool as ip_pool_module
    from src.core.rem.ip_pool import IPEntry, IPPool
    from src.core.rem.models import Environment, EnvKind, EnvStatus
    from src.core.rem.ui.edit_env_dialog import EditEnvDialog

    pool = IPPool(id="pool-1", name="主池")
    pool.add_entry(IPEntry(id="ip-1", address="10.0.0.8", protocol="socks5", port=1080))
    monkeypatch.setattr(
        ip_pool_module,
        "get_ip_pool_manager",
        lambda: SimpleNamespace(get_pool=lambda pool_id: None, list_pools=lambda: [pool]),
    )
    env = Environment(id=621, name="env", kind=EnvKind.BROWSER, provider="virtualbrowser", status=EnvStatus.READY)

    dialog = EditEnvDialog(env)
    qtbot.addWidget(dialog)

    assert dialog.proxy_entry_combo.isEnabled()
    assert dialog.proxy_entry_combo.count() == 1
    assert dialog.proxy_entry_combo.currentData() == "ip-1"


def test_edit_env_dialog_saves_selected_ip_when_env_has_no_proxy(qtbot, monkeypatch):
    import src.core.rem.ip_pool as ip_pool_module
    from src.core.rem.ip_pool import IPEntry, IPPool
    from src.core.rem.models import Environment, EnvKind, EnvStatus
    from src.core.rem.ui.edit_env_dialog import EditEnvDialog

    pool = IPPool(id="pool-1", name="主池")
    pool.add_entry(IPEntry(id="ip-1", address="10.0.0.8", protocol="socks5", port=1080))
    monkeypatch.setattr(
        ip_pool_module,
        "get_ip_pool_manager",
        lambda: SimpleNamespace(get_pool=lambda pool_id: None, list_pools=lambda: [pool]),
    )
    env = Environment(id=621, name="env", kind=EnvKind.BROWSER, provider="virtualbrowser", status=EnvStatus.READY)
    dialog = EditEnvDialog(env)
    qtbot.addWidget(dialog)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        dialog,
        "_run_action",
        lambda action, **kwargs: captured.update({"action": action, **kwargs}),
    )

    dialog._save()

    assert captured == {"action": "update_proxy_entry", "proxy_entry_id": "ip-1"}


def test_edit_env_worker_passes_proxy_value_to_manager(monkeypatch):
    import src.core.rem.manager as manager_module
    from src.core.rem.ui.edit_env_dialog import EditEnvWorker

    manager = SimpleNamespace(update_env=AsyncMock(return_value=True))
    monkeypatch.setattr(manager_module, "get_environment_manager", lambda: manager)

    results: list[tuple[bool, str]] = []
    worker = EditEnvWorker(
        env_id=7,
        action="update_proxy",
        proxy_value="http://127.0.0.1:8080",
    )
    worker.finished.connect(lambda success, message: results.append((success, message)))

    worker.run()

    manager.update_env.assert_awaited_once_with(7, proxy_value="http://127.0.0.1:8080")
    assert results == [(True, "代理已更新")]


def test_edit_env_worker_passes_randomize_fingerprint_flag(monkeypatch):
    import src.core.rem.manager as manager_module
    from src.core.rem.ui.edit_env_dialog import EditEnvWorker

    manager = SimpleNamespace(update_env=AsyncMock(return_value=True))
    monkeypatch.setattr(manager_module, "get_environment_manager", lambda: manager)

    results: list[tuple[bool, str]] = []
    worker = EditEnvWorker(env_id=9, action="refresh_fingerprint")
    worker.finished.connect(lambda success, message: results.append((success, message)))

    worker.run()

    manager.update_env.assert_awaited_once_with(9, randomize_fingerprint=True)
    assert results == [(True, "指纹已刷新")]


def test_edit_env_worker_passes_selected_proxy_entry_to_manager(monkeypatch):
    import src.core.rem.manager as manager_module
    from src.core.rem.ui.edit_env_dialog import EditEnvWorker

    manager = SimpleNamespace(update_env=AsyncMock(return_value=True))
    monkeypatch.setattr(manager_module, "get_environment_manager", lambda: manager)

    results: list[tuple[bool, str]] = []
    worker = EditEnvWorker(env_id=7, action="update_proxy_entry", proxy_entry_id="ip-2")
    worker.finished.connect(lambda success, message: results.append((success, message)))

    worker.run()

    manager.update_env.assert_awaited_once_with(7, proxy_entry_id="ip-2")
    assert results == [(True, "IP 已更新")]
