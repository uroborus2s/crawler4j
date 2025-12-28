
import asyncio
import os
import sys

import cv2
import numpy as np
from playwright.async_api import async_playwright

# Add src to path
sys.path.append(os.getcwd())
from src.utils.captcha_solver import CaptchaSolver


async def debug_scaling():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        print("Navigating...")
        await page.goto("https://passport.ctrip.com/user/login")
        
        # Trigger captcha
        print("Triggering captcha...")
        sms_texts = ["验证码登录", "手机号查单"]
        for txt in sms_texts:
            if await page.is_visible(f"text='{txt}'"):
                await page.click(f"text='{txt}'")
                break
        
        await page.fill("input[type='tel']", "18709299823")
        await page.click("text='发送验证码'")
        
        try:
            print("Waiting for slider...")
            slider_btn = ".cpt-drop-btn"
            await page.wait_for_selector(slider_btn, timeout=10000)
            await asyncio.sleep(2) 
            
            # Elements
            bg_el = page.locator("img.advise").first
            if not await bg_el.is_visible():
                bg_el = page.locator(".cpt-img-cal-box img").first
            
            track_el = page.locator(".cpt-bg-bar").first
            
            # Get Bounding Boxes
            bg_box = await bg_el.bounding_box()
            track_box = await track_el.bounding_box()
            slider_box = await page.locator(slider_btn).bounding_box()
            
            print(f"BG Image Box: {bg_box}")
            print(f"Track Box: {track_box}")
            print(f"Slider Box: {slider_box}")
            
            # Screenshot and Solve
            png_bytes = await bg_el.screenshot()
            
            offset = CaptchaSolver.solve_slider(png_bytes, debug=True)
            print(f"Solver Detected Offset (in Image Pixels): {offset}")
            
            # Check Image Size
            nparr = np.frombuffer(png_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            h, w, _ = img.shape
            print(f"Actual Screenshot Size: {w}x{h}")
            
            # Ratios
            if bg_box and track_box:
                # If image is 320px wide in CSS, and track is 280px wide?
                width_ratio = track_box['width'] / bg_box['width']
                print(f"Track/Image Width Ratio: {width_ratio}")
                
                # Check intrinsic image size
                # Usually we care about how many pixels of Drag correspond to 1 pixel of Image
                
                # If Offset inside Image is X pixels.
                # Image is Displayed at W_css pixels.
                # Image Natural Width is W_natural pixels. (Screenshot should match W_natural usually if DPR=1)
                
                # Drag Track is L_css pixels long.
                
                # Usually: 
                # Percentage = offset / W_natural
                # Drag_Distance = Percentage * L_css ? No.
                
                # Usually the image IS the track background.
                # So if I identify the hole is at X pixels in a W_natural image (Screenshot).
                # And the Screenshot Size == Displayed Size (which verified).
                # Then I should drag X pixels.
                
                # BUT, if the KNOB starts at x=0 of the track... 
                # Does x=0 of track align with x=0 of image?
                # Usually yes.
                
                # Let's see the numbers.
                
        except Exception as e:
            print(f"Error: {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_scaling())
