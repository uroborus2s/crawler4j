import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.core.browser_api import BrowserAPI
from src.utils.storage import CtripAccountRepository, EnvironmentRepository, LaborAccountRepository


def sync_environments():
    """Sync environments from BitBrowser to local database."""
    print("Starting environment synchronization...")
    
    env_repo = EnvironmentRepository()
    ctrip_repo = CtripAccountRepository()
    labor_repo = LaborAccountRepository()
    
    page = 1
    page_size = 50
    total_synced = 0
    total_skipped = 0
    
    while True:
        print(f"Fetching page {page}...")
        result = BrowserAPI.list_profiles(page_num=page, page_size=page_size)
        
        if not result:
            print("Failed to fetch profiles or no connection to Browser API.")
            break
            
        profiles = result.get("list", [])
        total = result.get("total", 0)
        
        if not profiles:
            break
            
        for profile in profiles:
            profile_id = profile["id"]
            name = profile["name"]
            
            # Check if exists
            if env_repo.count("browser_profile_id = ?", (profile_id,)) > 0:
                print(f"Skipping existing profile: {name} ({profile_id})")
                total_skipped += 1
                continue
                
            # Try to match accounts based on name if it looks like a phone number
            # Using simple heuristic: if name is 11 digits, treated as phone
            ctrip_id = None
            labor_id = None
            
            # Clean name for matching (remove whitespace)
            clean_name = name.strip()
            
            if clean_name.isdigit() and len(clean_name) == 11:
                # Try to find in Ctrip accounts
                ctrip = ctrip_repo.get_by_phone(clean_name)
                if ctrip:
                    ctrip_id = ctrip["id"]
                    print(f"  Matched Ctrip Account: {clean_name}")
                
                # Check Labor accounts? (Usually labor accounts are different phones, but check anyway)
                # But labor repo doesn't have get_by_phone exposed easily? 
                # Actually let's look at storage.py again. LaborAccountRepository doesn't store phone directly as primary lookup?
                # It has 'phone' column. BaseRepository has get_all, count.
                # I can iterate or just assume if it matched Ctrip it's fine.
                # Let's keep it simple: strict sync of environments first.
            
            try:
                env_repo.create(
                    ctrip_account_id=ctrip_id,
                    labor_account_id=labor_id,
                    browser_profile_id=profile_id,
                    browser_type="bitbrowser",
                    daily_open_limit=50 
                )
                print(f"Synced profile: {name} ({profile_id})")
                total_synced += 1
            except Exception as e:
                print(f"Error syncing {name}: {e}")
        
        if len(profiles) < page_size:
            break
            
        page += 1
        
    print(f"\nSync complete.")
    print(f"Total synced: {total_synced}")
    print(f"Total skipped: {total_skipped}")

if __name__ == "__main__":
    sync_environments()
