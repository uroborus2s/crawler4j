
import time

from playwright.sync_api import sync_playwright


def inspect():
    with sync_playwright() as p:
        # Headless=False so we can see what's happening
        browser = p.chromium.launch(headless=True) 
        page = browser.new_page()
        
        print("Navigating to Ctrip Login...")
        page.goto("https://passport.ctrip.com/user/login", timeout=60000)
        
        # Switch to Code Login
        sms_texts = ["验证码登录", "手机号查单"]
        for txt in sms_texts:
            if page.is_visible(f"text='{txt}'"):
                print(f"Clicking {txt}")
                page.click(f"text='{txt}'")
                break
        
        time.sleep(2)
        
        print("Filling phone number...")
        phone = "18709299823"
        
        phone_input_sel = "input[data-testid='telInput']"
        # Fallbacks
        if not page.is_visible(phone_input_sel):
             phone_input_sel = "input[type='tel']"
        
        if page.is_visible(phone_input_sel):
             page.fill(phone_input_sel, phone)
        else:
             print("Could not find phone input!")
             return

        time.sleep(1)
        
        print("Clicking Get Code...")
        # Text selector
        get_code_btn = "text='发送验证码'"
        if not page.is_visible(get_code_btn):
            get_code_btn = "text='获取验证码'"
            
        if page.is_visible(get_code_btn):
            page.click(get_code_btn)
        else:
            print("Could not find Get Code button")
            return
        
        print("Waiting for Captcha Slider...")
        try:
            # Wait for slider knob
            page.wait_for_selector(".cpt-drop-btn", timeout=10000)
            print("Captch appeared!")
            time.sleep(3) # Wait for animation
            
            # Dump the captcha container
            print("\n--- Captcha Container HTML ---")
            
            # Try to find the container
            # The user image shows a popup modal. 
            # Often generic class .cpt-panel or similar.
            # Let's inspect all images in the page to find the one that looks like a background
            images = page.locator("img").all()
            print(f"Found {len(images)} images")
            
            for i, img in enumerate(images):
                if img.is_visible():
                    src = img.get_attribute("src")
                    cls = img.get_attribute("class")
                    # approximate size
                    box = img.bounding_box()
                    if box and box['width'] > 200 and box['height'] > 100:
                        print(f"Candidate Img {i}: Class='{cls}', Src='{src}', Size={box['width']}x{box['height']}")
                        # Dump parent HTML
                        print(img.locator("..").inner_html())
            
            page.screenshot(path="debug_captcha_repro.png")
            print("Screenshot saved to debug_captcha_repro.png")
            
        except Exception as e:
            print(f"Captcha verification failed or did not appear: {e}")
            page.screenshot(path="debug_captcha_fail.png")

        browser.close()

if __name__ == "__main__":
    inspect()
