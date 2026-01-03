"""Data refresh thread.

Fetches status from browser API and local DB in background to avoid UI freeze.
"""

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.browser_api import BrowserAPI
from src.utils.logger import logger
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

    def run(self):
        """Execute data refresh."""
        try:
            # 1. Fetch remote profiles
            # Use large page size to get all
            remote_data = BrowserAPI.list_profiles(page_size=1000)
            
            # Handle connection failure
            remote_list = []
            connection_failed = False
            if remote_data is None:
                connection_failed = True
                # Can't log heavily here, but we proceed with local data
            else:
                remote_list = remote_data.get("list", []) or []

            remote_map = {p["id"]: p for p in remote_list}

            # 2. Get local DB envs
            local_envs = self.env_repo.get_all(limit=1000)
            local_map = {env["browser_profile_id"]: env for env in local_envs}

            # 3. Sync status (Skipped if connection failed)
            if not connection_failed:
                self._sync_status(local_map, remote_map)
                
                # 4. Reload local if we might have changed status during sync
                if self.cleanup:
                     local_envs = self.env_repo.get_all(limit=1000)
                     local_map = {env["browser_profile_id"]: env for env in local_envs}

            # 5. Build display data
            # Union of IDs
            all_ids = set(remote_map.keys()) | set(local_map.keys())
            display_data = []

            for pid in all_ids:
                row = self._build_row_data(pid, remote_map, local_map)
                # If connection failed, mark as unknown status for remote-only (shouldn't exist)
                # For local items, _build_row_data handles missing remote
                display_data.append(row)

            # Sort by seq if available, or name
            # display_data.sort(key=lambda x: x.get("seq", 999999))
            
            self.data_loaded.emit(display_data)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(str(e))

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
                # 远程还在跑，本地可能是 running 或 idle (错位)
                # 或者是 cleanup 模式要求全部关闭
                BrowserAPI.close_browser(pid)
                self.env_repo.update_status(env_id, "idle")
                self.env_repo.update_connection_info(env_id, None, None, None)
                remote_profile["status"] = "Closed (Cleanup)"
                logger.info(f"Cleanup: Closed running browser for ENV-{env_id}")
            elif local_env.get("status") in ["running", "active"]:
                # 远程已经关了，但本地还显示运行中 (程序崩溃残留)
                self.env_repo.update_status(env_id, "idle")
                self.env_repo.update_connection_info(env_id, None, None, None)
                # 🔴 重要：同时释放劳保账号锁定
                if self.labor_repo:
                    released = self.labor_repo.force_unlock_by_env(env_id)
                    if released > 0:
                        logger.info(f"Cleanup: Released {released} labor account locks for ENV-{env_id}")
                logger.info(f"Cleanup: Reset stale local status for ENV-{env_id}")

    def _build_row_data(
        self, pid: str, remote_map: dict, local_map: dict
    ) -> dict:
        """构建单行显示数据。"""
        # Ensure we don't mutate the original remote map if we need to modify it
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

        # 账号状态 (仅展示携程账号)
        ctrip_phone = "-"
        if local:
            ctrip_id = local.get("ctrip_account_id")
            if ctrip_id:
                ctrip_account = self.ctrip_repo.get_by_id(ctrip_id)
                if ctrip_account:
                    code = ctrip_account.get("country_code", "+86")
                    num = ctrip_account.get("phone_number", "")
                    # Full phone for tooltip
                    full_phone = f"{code}{num}"
                    ctrip_phone = full_phone
                    # Hack: Attach full phone to be used by UI wrapper if needed? 
                    # Actually, we can return it in a hidden field or assume UI handles it?
                    # Since DataTable is generic, let's keep it simple. 
                    # We can use a custom renderer or just rely on the fact that we return dict.

        raw_status = local.get("status") if local else remote.get("status", "Unknown")
        browser_status = self._translate_status(raw_status)

        # Time formatting
        last_run = "-"
        if local and local.get("last_run_at"):
            last_run = self._format_time(local.get("last_run_at"))

        last_open_date = "-"
        if local and local.get("last_open_date"):
             # last_open_date is likely date object or str YYYY-MM-DD
             last_open_date = str(local.get("last_open_date"))

        return {
            "id": pid,
            "name": remote["name"],
            "group": remote["group"],
            "proxy_ip": remote["proxy_ip"],
            "system_type": system_type,
            "ctrip_account": ctrip_phone,
            "browser_status": browser_status,
            "created_at": remote.get("created_at") or "-",
            "last_active": last_run,
            "last_open": last_open_date,
            "daily_usage": local.get("daily_open_count") if local else 0,
            "max_usage": local.get("daily_open_limit") if local else 0,
            "actions": "",
            "raw_remote": remote_map.get(pid),
            "raw_local": local,
        }

    def _format_time(self, time_str: str) -> str:
        """Format timestamp to YYYY/MM/DD HH:mm:ss."""
        if not time_str:
            return "-"
        try:
            from datetime import datetime
            # Handle ISO format
            if isinstance(time_str, str):
                dt = datetime.fromisoformat(time_str)
            else:
                dt = time_str
            
            # Convert to local time if naive (assume UTC if from DB/ISO) usually
            # But here we stick to simple formatting as requirements usually imply "display what is stored"
            # or "current system timezone". If stored as UTC, we need conversion.
            # Assuming stored as local or naive-as-local for simplicity unless logic dictates otherwise.
            # User request: "current system timezone".
            # If datetime is timezone-aware, astimezone() converts it.
            # If naive, assume local?
            
            return dt.strftime("%Y/%m/%d %H:%M:%S")
        except Exception:
            return str(time_str)

    def _translate_status(self, status: str) -> str:
        """Translate status to Chinese."""
        if not status:
             return "未知"
        s = str(status).lower()
        mapping = {
            "idle": "空闲",
            "running": "运行中",
            "active": "运行中",
            "open": "运行中",
            "opened": "运行中",
            "error": "错误",
            "disconnected": "断开",
        }
        return mapping.get(s, status)

    def _mask_phone(self, phone: str) -> str:
        if len(phone) >= 7:
            return f"{phone[:3]}***{phone[-2:]}"
        return phone
