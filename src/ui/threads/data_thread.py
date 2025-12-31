"""Data refresh thread.

Fetches status from browser API and local DB in background to avoid UI freeze.
"""

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.browser_api import BrowserAPI
from src.utils.storage import (
    CtripAccountRepository,
    EnvironmentRepository,
    LaborAccountRepository,
)


class DataRefreshThread(QThread):
    """Thread to fetch environment data."""

    data_loaded = pyqtSignal(list)  # Emits list of row dicts
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        env_repo=None,
        ctrip_repo=None,
        labor_repo=None,
        proxy_repo=None,
        cleanup=False,
    ):
        super().__init__()
        self.env_repo = env_repo or EnvironmentRepository()
        self.ctrip_repo = ctrip_repo or CtripAccountRepository()
        self.labor_repo = labor_repo or LaborAccountRepository()
        self.proxy_repo = proxy_repo  # Not used yet but passed for consistency
        self.cleanup = cleanup

    def _sync_status(
        self, local_map: dict, remote_map: dict
    ) -> None:
        """同步本地和远程浏览器状态。
        
        仅在 cleanup=True 模式下关闭运行中的浏览器。
        不再根据远程状态覆盖本地状态，状态完全由调度器控制。
        """
        if not self.cleanup:
            return  # 非清理模式，不做任何同步

        for pid, local_env in local_map.items():
            remote_profile = remote_map.get(pid)
            if not remote_profile:
                continue

            r_status = str(remote_profile.get("status", "")).lower()
            is_remote_running = r_status in ["open", "opened", "active", "running"]
            env_id = local_env["id"]

            if is_remote_running:
                BrowserAPI.close_browser(pid)
                self.env_repo.update_status(env_id, "idle")
                self.env_repo.update_connection_info(env_id, None, None, None)
                remote_profile["status"] = "Closed (Cleanup)"

    def _build_row_data(
        self, pid: str, remote_map: dict, local_map: dict
    ) -> dict:
        """构建单行显示数据。"""
        remote = remote_map.get(pid) or {
            "id": pid,
            "name": "未知 (Local Only)",
            "group": "-",
            "proxy_ip": "-",
            "status": "Error",
            "created_at": "-",
        }
        local = local_map.get(pid)

        # 系统类型
        if local and remote_map.get(pid):
            system_type = "crawler4j系统"
        elif local:
            system_type = "error"
        else:
            system_type = "无"

        # 账号状态
        ctrip_phone, labor_phone = "-", "-"
        if local:
            ctrip_id = local.get("ctrip_account_id")
            if ctrip_id:
                ctrip_account = self.ctrip_repo.get_by_id(ctrip_id)
                if ctrip_account:
                    code = ctrip_account.get("country_code", "+86")
                    num = ctrip_account.get("phone_number", "")
                    ctrip_phone = self._mask_phone(f"{code}{num}")

            labor_id = local.get("labor_account_id")
            if labor_id:
                labor_account = self.labor_repo.get_by_id(labor_id)
                if labor_account:
                    labor_phone = labor_account["phone"]

        local_status = (
            f"{ctrip_phone}/{labor_phone}"
            if ctrip_phone != "-" or labor_phone != "-"
            else "-"
        )

        browser_status = (
            local.get("status", remote.get("status", "Unknown"))
            if local
            else remote.get("status", "Unknown")
        )

        return {
            "id": pid,
            "name": remote["name"],
            "group": remote["group"],
            "proxy_ip": remote["proxy_ip"],
            "system_type": system_type,
            "local_status": local_status,
            "browser_status": browser_status,
            "created_at": remote.get("created_at") or "-",
            "actions": "",
            "raw_remote": remote_map.get(pid),
            "raw_local": local,
        }

    def run(self):
        try:
            # 1. 获取远程配置
            remote_result = BrowserAPI.list_profiles(page_num=1, page_size=100)
            remote_profiles = remote_result.get("list", [])
            remote_map = {p["id"]: p for p in remote_profiles}

            # 2. 获取本地配置
            local_envs = self.env_repo.get_all(limit=1000)
            local_map = {env["browser_profile_id"]: env for env in local_envs}

            # 3. 同步状态
            self._sync_status(local_map, remote_map)

            # 4. 刷新本地数据
            local_envs = self.env_repo.get_all(limit=1000)
            local_map = {env["browser_profile_id"]: env for env in local_envs}

            # 5. 构建显示数据
            all_ids = set(remote_map.keys()) | set(local_map.keys())
            display_data = [
                self._build_row_data(pid, remote_map, local_map) for pid in all_ids
            ]

            self.data_loaded.emit(display_data)

        except Exception as e:
            self.error_occurred.emit(str(e))

    def _mask_phone(self, phone: str) -> str:
        if len(phone) >= 7:
            return f"{phone[:3]}***{phone[-2:]}"
        return phone
