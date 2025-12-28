
import asyncio
import logging

from src.automation.driver import AutomationDriver
from src.automation.workflows.ctrip_login import CtripLoginWorkflow
from src.core.models.ctrip_account import CtripAccount
from src.utils.logger import LogLevel, logger

# Setup basic logging to console for this test
logging.basicConfig(level=logging.INFO)

async def test_ctrip_login():
    """Manual test for Ctrip login workflow."""
    
    # 1. Configuration
    # REPLACE WITH YOUR ACTUAL PROFILE ID AND CREDENTIALS
    PROFILE_ID = "YOUR_BROWSER_PROFILE_ID"
    PHONE = "13800138000"
    
    # SMS Platform Config (HaoMa)
    SMS_URL = "http://api.haoma.com/sms"
    SMS_KEY = "YOUR_API_TOKEN" 
    SMS_TYPE = "haoma"
    
    print(f"Starting test with Profile: {PROFILE_ID}, Phone: {PHONE}")
    
    # 2. Create Account Object
    account = CtripAccount(
        phone=PHONE,
        sms_platform_url=SMS_URL,
        sms_platform_key=SMS_KEY,
        sms_platform_type=SMS_TYPE
    )
    
    # 3. Run Workflow
    try:
        async with AutomationDriver.connect(PROFILE_ID) as page:
            workflow = CtripLoginWorkflow(page)
            
            print("--- Executing Login Workflow ---")
            success = await workflow.login(account)
            
            if success:
                print(">>> LOGIN SUCCESS <<<")
            else:
                print(">>> LOGIN FAILED <<<")
                
    except Exception as e:
        print(f"Test failed with error: {e}")

if __name__ == "__main__":
    # Ensure this is run in an environment where 'src' is in pythonpath
    # export PYTHONPATH=$PYTHONPATH:.
    try:
        asyncio.run(test_ctrip_login())
    except KeyboardInterrupt:
        pass
