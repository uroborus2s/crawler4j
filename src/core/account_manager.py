"""Account manager module.

Handles scheduling logic for Ctrip and Labor account pools.
"""

from src.core.models.ctrip_account import CtripAccount
from src.core.models.labor_account import LaborAccount
from src.core.models.environment import Environment, EnvironmentStatus
from src.utils.storage import (
    CtripAccountRepository,
    LaborAccountRepository,
    EnvironmentRepository,
)


class AccountManager:
    """Manages account pools and environment scheduling.
    
    Scheduling Logic:
    1. Select an active Ctrip account
    2. Check if it has an existing environment
    3. If yes: start the environment
    4. If no: find an unbound active Labor account, create new environment
    5. If Ctrip account is banned: delete environment, blacklist account
    """
    
    def __init__(self):
        self.ctrip_repo = CtripAccountRepository()
        self.labor_repo = LaborAccountRepository()
        self.env_repo = EnvironmentRepository()
    
    def get_next_environment(self) -> Environment | None:
        """Get the next available environment for task execution.
        
        Returns:
            Environment if one is available, None otherwise.
        """
        # Get active Ctrip accounts
        ctrip_accounts = self.ctrip_repo.get_active()
        
        for ctrip_data in ctrip_accounts:
            ctrip = CtripAccount.from_dict(ctrip_data)
            
            # Check if this account has an existing environment
            env_data = self.env_repo.get_by_ctrip_account(ctrip.id)
            
            if env_data:
                env = Environment.from_dict(env_data)
                if env.is_idle:
                    return env
            else:
                # No environment - try to create one
                env = self._create_environment_for_ctrip(ctrip)
                if env:
                    return env
        
        return None
    
    def _create_environment_for_ctrip(self, ctrip: CtripAccount) -> Environment | None:
        """Create a new environment for a Ctrip account.
        
        Args:
            ctrip: The Ctrip account to create environment for.
            
        Returns:
            New Environment if successful, None otherwise.
        """
        # Find an unbound active Labor account
        labor_accounts = self.labor_repo.get_active_unbound()
        
        if not labor_accounts:
            return None
        
        labor_data = labor_accounts[0]
        labor = LaborAccount.from_dict(labor_data)
        
        # Generate browser profile ID (will be created by browser API)
        browser_profile_id = f"profile_{ctrip.id}_{labor.id}"
        
        # Create environment
        env_id = self.env_repo.create(
            ctrip_account_id=ctrip.id,
            labor_account_id=labor.id,
            browser_profile_id=browser_profile_id,
        )
        
        return Environment(
            id=env_id,
            ctrip_account_id=ctrip.id,
            labor_account_id=labor.id,
            browser_profile_id=browser_profile_id,
            status=EnvironmentStatus.IDLE,
        )
    
    def start_environment(self, env_id: int) -> bool:
        """Mark environment as running.
        
        Args:
            env_id: Environment ID.
            
        Returns:
            True if successful.
        """
        return self.env_repo.update_status(env_id, "running")
    
    def stop_environment(self, env_id: int) -> bool:
        """Mark environment as idle.
        
        Args:
            env_id: Environment ID.
            
        Returns:
            True if successful.
        """
        return self.env_repo.update_status(env_id, "idle")
    
    def blacklist_ctrip_account(self, ctrip_account_id: int) -> bool:
        """Blacklist a Ctrip account and delete its environment.
        
        Called when account is banned or logged out.
        
        Args:
            ctrip_account_id: Ctrip account ID.
            
        Returns:
            True if successful.
        """
        # Delete environment first
        env_data = self.env_repo.get_by_ctrip_account(ctrip_account_id)
        if env_data:
            self.env_repo.delete(env_data["id"])
        
        # Blacklist the account
        return self.ctrip_repo.update_status(ctrip_account_id, "blacklisted")
    
    def update_labor_stats(
        self,
        labor_account_id: int,
        completed: int = 0,
        discarded: int = 0,
        approved: int = 0,
        rejected: int = 0,
    ) -> bool:
        """Update statistics for a Labor account.
        
        Args:
            labor_account_id: Labor account ID.
            completed: Number of completed tasks to add.
            discarded: Number of discarded tasks to add.
            approved: Number of approved tasks to add.
            rejected: Number of rejected tasks to add.
            
        Returns:
            True if successful.
        """
        return self.labor_repo.update_stats(
            labor_account_id,
            completed=completed,
            discarded=discarded,
            approved=approved,
            rejected=rejected,
        )
    
    def get_running_count(self) -> int:
        """Get count of currently running environments."""
        return self.env_repo.get_running_count()
    
    def get_active_ctrip_count(self) -> int:
        """Get count of active Ctrip accounts."""
        return self.ctrip_repo.count("status = 'active'")
    
    def get_active_labor_count(self) -> int:
        """Get count of active Labor accounts."""
        return self.labor_repo.count("status = 'active'")
