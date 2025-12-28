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
    
    data_loaded = pyqtSignal(list) # Emits list of row dicts
    error_occurred = pyqtSignal(str)
    
    
    def __init__(self, env_repo=None, ctrip_repo=None, labor_repo=None, proxy_repo=None, cleanup=False):
        super().__init__()
        self.env_repo = env_repo or EnvironmentRepository()
        self.ctrip_repo = ctrip_repo or CtripAccountRepository()
        self.labor_repo = labor_repo or LaborAccountRepository()
        self.proxy_repo = proxy_repo # Not used yet but passed for consistency
        self.cleanup = cleanup

        
    def run(self):
        try:
            # 1. Fetch remote profiles
            remote_result = BrowserAPI.list_profiles(page_num=1, page_size=100)
            remote_profiles = remote_result.get("list", [])
            remote_map = {p["id"]: p for p in remote_profiles}
            
            # 2. Fetch local system bindings
            local_envs = self.env_repo.get_all(limit=1000)
            local_map = {env["browser_profile_id"]: env for env in local_envs}
            
            # == SYNC LOGIC START ==
            # Update local DB based on remote status
            for pid, local_env in local_map.items():
                remote_profile = remote_map.get(pid)
                if not remote_profile:
                    continue
                    
                # Determine remote status (BitBrowser specific)
                # Assuming 'status' field exists. 
                # If API returns 'Open', 'Active' etc.
                r_status = str(remote_profile.get("status", "")).lower()
                is_remote_running = r_status in ["open", "opened", "active", "running"]
                
                local_status = local_env.get("status", "idle")
                env_id = local_env["id"]
                
                # Cleanup Mode: Force Close if running
                if self.cleanup and is_remote_running:
                    # Close remote browser
                    BrowserAPI.close_browser(pid)
                    # Force idle in DB
                    self.env_repo.update_status(env_id, "idle")
                    self.env_repo.update_connection_info(env_id, None, None, None)
                    # Update local var for display logic below
                    is_remote_running = False 
                    remote_profile["status"] = "Closed (Cleanup)" 
                
                # Normal Sync Mode
                elif is_remote_running and local_status != "running":
                    # Remote is running, local is not -> Sync to Running
                    self.env_repo.update_status(env_id, "running")
                    # We might not have WS endpoint here if we didn't open it ourselves, 
                    # but status at least is synced.
                    
                elif not is_remote_running and local_status == "running":
                    # Remote is closed, local says running -> Sync to Idle (Crash/External Close)
                    self.env_repo.update_status(env_id, "idle")
                    self.env_repo.update_connection_info(env_id, None, None, None)
                    
            # Refresh local map after sync to show correct status in UI
            local_envs = self.env_repo.get_all(limit=1000)
            local_map = {env["browser_profile_id"]: env for env in local_envs}
            # == SYNC LOGIC END ==
            
            # 3. Merge IDs (Union of both)
            all_ids = set(remote_map.keys()) | set(local_map.keys())
            
            display_data = []
            for pid in all_ids:
                remote = remote_map.get(pid)
                local = local_map.get(pid)
                
                # Default values for missing remote
                if not remote:
                    remote = {
                        "id": pid, "name": "未知 (Local Only)", "group": "-", 
                        "proxy_ip": "-", "status": "Error", "created_at": "-"
                    }
                
                # Logic: System Type Display
                system_type = "无"
                if local and remote_map.get(pid):
                    system_type = "crawler4j系统"
                elif local and not remote_map.get(pid):
                    system_type = "error"
                
                # Local Status (Accounts)
                local_status = "-"
                ctrip_phone = "-"
                labor_phone = "-"
                
                if local:
                    ctrip_id = local.get("ctrip_account_id")
                    if ctrip_id:
                        ctrip_account = self.ctrip_repo.get_by_id(ctrip_id)
                        if ctrip_account: 
                            ctrip_phone = self._mask_phone(ctrip_account["phone"])
                        
                    labor_id = local.get("labor_account_id")
                    if labor_id:
                        labor_account = self.labor_repo.get_by_id(labor_id)
                        if labor_account: 
                            labor_phone = labor_account["phone"]
                    
                    if ctrip_phone != "-" or labor_phone != "-":
                        local_status = f"{ctrip_phone}/{labor_phone}"

                row = {
                    "id": pid,
                    "name": remote["name"],
                    "group": remote["group"],
                    "proxy_ip": remote["proxy_ip"],
                    "system_type": system_type,
                    "local_status": local_status,
                    "browser_status": remote.get("status", "Unknown"), # Use remote status directly? Or local db status? 
                    # User asked to see DB status? 
                    # Actually, if we just synced, they should be same. 
                    # But maybe we should prefer Local DB status if it has more info like 'error'.
                    # For now, let's show Remote Status as 'browser_status', but maybe add a 'db_status' column if needed.
                    # Wait, the UI column is 'status'. 
                    # The environments_page table columns are: ID, Name, Group, Proxy, System, Accounts, Status, Created, Actions.
                    # 'Status' usually refers to Browser Status.
                    "created_at": remote.get("created_at") or "-",
                    "actions": "", 
                    "raw_remote": remote_map.get(pid),
                    "raw_local": local
                }
                display_data.append(row)
            
            self.data_loaded.emit(display_data)
            
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _mask_phone(self, phone: str) -> str:
        if len(phone) >= 7:
            return f"{phone[:3]}***{phone[-2:]}"
        return phone
