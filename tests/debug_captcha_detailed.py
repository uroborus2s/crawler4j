#!/usr/bin/env python3
"""
详细调试携程滑块验证码 - 捕获图片并分析问题
"""
import asyncio
import os
import sys
from datetime import datetime

import cv2
import numpy as np
from playwright.async_api import async_playwright

sys.path.insert(0, os.getcwd())
from src.utils.captcha_solver import CaptchaSolver


async def debug_captcha():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_dir = f"debug_output_{timestamp}"
    os.makedirs(debug_dir, exist_ok=True)
    print(f"调试输出目录: {debug_dir}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            device_scale_factor=1  # 强制 DPR=1
        )
        page = await context.new_page()
        
        print("1. 导航到登录页...")
        await page.goto("https://passport.ctrip.com/user/login")
        await asyncio.sleep(2)
        
        # 切换到验证码登录
        print("2. 触发验证码...")
        for txt in ["验证码登录", "手机号查单"]:
            if await page.is_visible(f"text='{txt}'"):
                await page.click(f"text='{txt}'")
                await asyncio.sleep(0.5)
                break
        
        # 输入手机号
        await page.fill("input[type='tel']", "18888888888")
        await page.click("text='发送验证码'")
        
        # 等待验证码出现
        print("3. 等待滑块验证码...")
        try:
            await page.wait_for_selector(".cpt-drop-btn", timeout=10000)
        except:
            print("❌ 未检测到滑块验证码")
            await browser.close()
            return
        
        await asyncio.sleep(1.5)  # 等待图片加载
        
        # 截取整个验证码区域
        print("4. 捕获验证码元素...")
        
        # 获取各元素信息
        selectors = {
            "slider_btn": ".cpt-drop-btn",
            "bg_img": "img.advise",
            "bg_img_alt": ".cpt-img-cal-box img",
            "slider_piece": ".cpt-img-double img",
            "track": ".cpt-bg-bar",
            "container": ".cpt-img-cal-box"
        }
        
        element_info = {}
        for name, sel in selectors.items():
            try:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    box = await el.bounding_box()
                    element_info[name] = box
                    print(f"  {name}: {box}")
                    
                    # 截图保存
                    screenshot = await el.screenshot()
                    with open(f"{debug_dir}/{name}.png", "wb") as f:
                        f.write(screenshot)
            except Exception as e:
                print(f"  {name}: 获取失败 - {e}")
        
        # 获取背景图的原始 URL
        print("\n5. 获取图片信息...")
        try:
            img_info = await page.evaluate("""() => {
                const img = document.querySelector('img.advise');
                if (img) {
                    return {
                        src: img.src,
                        naturalWidth: img.naturalWidth,
                        naturalHeight: img.naturalHeight,
                        displayWidth: img.clientWidth,
                        displayHeight: img.clientHeight
                    };
                }
                return null;
            }""")
            print(f"  背景图信息: {img_info}")
        except Exception as e:
            print(f"  获取图片信息失败: {e}")
        
        # 分析背景图
        print("\n6. 分析背景图...")
        bg_path = f"{debug_dir}/bg_img.png"
        if os.path.exists(bg_path):
            with open(bg_path, "rb") as f:
                bg_bytes = f.read()
            
            # 加载滑块图（如果有）
            slider_bytes = None
            slider_path = f"{debug_dir}/slider_piece.png"
            if os.path.exists(slider_path):
                with open(slider_path, "rb") as f:
                    slider_bytes = f.read()
            
            # 调用识别
            offset, img_w = CaptchaSolver.solve_slider(bg_bytes, slider_bytes, debug=True)
            print(f"  识别结果: offset={offset}, img_w={img_w}")
            
            # 加载图片用于可视化
            img = cv2.imdecode(np.frombuffer(bg_bytes, np.uint8), cv2.IMREAD_COLOR)
            if offset > 0:
                # 画出识别位置
                cv2.line(img, (offset, 0), (offset, img.shape[0]), (0, 255, 0), 2)
                cv2.circle(img, (offset, img.shape[0]//2), 5, (0, 0, 255), -1)
            cv2.imwrite(f"{debug_dir}/result_marked.png", img)
            print(f"  已保存标记图: {debug_dir}/result_marked.png")
        
        # 获取HTML结构
        print("\n7. 获取HTML结构...")
        try:
            full_html = await page.content()
            # 尝试只获取验证码部分
            captcha_html = await page.inner_html("body") 
            # 查找特定容器
            for sel in [".cpt-img-cal-box", ".cpt-drop-box", ".cpt-bg-img"]:
                try:
                    if await page.is_visible(sel):
                        captcha_html = await page.inner_html(sel)
                        print(f"  容器 {sel} HTML:\n{captcha_html}")
                        break
                except:
                    pass
        except Exception as e:
            print(f"  获取HTML失败: {e}")

        # print("\n7. 按任意键关闭浏览器...")
        # input()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_captcha())

