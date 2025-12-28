
import asyncio
import logging

from playwright.async_api import async_playwright

from src.automation.workflows.ctrip_login import CtripLoginWorkflow
from src.core.models.ctrip_account import CtripAccount

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


def input_callback_mock(title, label, default):
    print(f"\n[MOCK INPUT] {title} - {label}")
    if "手机号" in label:
        return "18709299823"
    if "验证码" in label:
        return "123456" # Mock code to proceed or let it fail at input step
    return default


async def verify():
    async with async_playwright() as p:
        # Launch browser (Headless=False to see the slider move)
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        workflow = CtripLoginWorkflow(page)
        
        print("Starting Login Verification...")
        # Simulate login with no account, relying on input callback
        result = await workflow.login(account=None, input_callback=input_callback_mock)
        
        if result:
            print(f"Login Success! Phone: {result}")
        else:
            print("Login Failed or Cancelled.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(verify())
