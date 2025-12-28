#!/usr/bin/env python3
"""
滑块验证码问题全面验证脚本

验证点：
1. 图片获取 - 选择器是否正确，图片是否完整
2. ddddocr 调用 - 参数顺序、simple_target 参数
3. 坐标转换 - DPR 缩放、像素到 CSS 的转换
4. 拖动距离计算 - 中心点 vs 左边缘

用法: python tests/verify_captcha_issues.py
"""
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

import cv2
import ddddocr
import numpy as np
from playwright.async_api import async_playwright

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class CaptchaVerifier:
    """验证滑块验证码识别的各个环节"""
    
    def __init__(self, debug_dir: str):
        self.debug_dir = debug_dir
        self.results = {}
        
    def log(self, msg: str, level: str = "INFO"):
        """日志输出"""
        icon = {"INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌", "OK": "✅"}.get(level, "")
        print(f"{icon} [{level}] {msg}")
        
    def verify_ddddocr_params(self, bg_bytes: bytes, slider_bytes: bytes | None):
        """验证 ddddocr 调用参数"""
        self.log("验证 ddddocr 参数...")
        
        det = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)
        
        # 解码图片获取尺寸
        bg_arr = np.frombuffer(bg_bytes, np.uint8)
        bg_img = cv2.imdecode(bg_arr, cv2.IMREAD_COLOR)
        if bg_img is None:
            self.log("背景图解码失败！", "ERROR")
            return None
            
        bg_h, bg_w = bg_img.shape[:2]
        self.log(f"  背景图尺寸: {bg_w} x {bg_h}")
        self.results["bg_size"] = (bg_w, bg_h)
        
        if slider_bytes:
            slider_arr = np.frombuffer(slider_bytes, np.uint8)
            slider_img = cv2.imdecode(slider_arr, cv2.IMREAD_UNCHANGED)
            if slider_img is not None:
                s_h, s_w = slider_img.shape[:2]
                self.log(f"  滑块图尺寸: {s_w} x {s_h}")
                self.results["slider_size"] = (s_w, s_h)
                
                # 检查是否有 alpha 通道
                has_alpha = len(slider_img.shape) == 3 and slider_img.shape[2] == 4
                self.log(f"  滑块图有透明通道: {has_alpha}")
                self.results["slider_has_alpha"] = has_alpha
        
        # 测试不同的 simple_target 值
        results_simple_true = None
        results_simple_false = None
        
        if slider_bytes:
            self.log("\n  测试 simple_target=True:")
            try:
                results_simple_true = det.slide_match(slider_bytes, bg_bytes, simple_target=True)
                self.log(f"    结果: {results_simple_true}", "OK" if results_simple_true else "WARN")
            except Exception as e:
                self.log(f"    错误: {e}", "ERROR")
                
            self.log("  测试 simple_target=False:")
            try:
                results_simple_false = det.slide_match(slider_bytes, bg_bytes, simple_target=False)
                self.log(f"    结果: {results_simple_false}", "OK" if results_simple_false else "WARN")
            except Exception as e:
                self.log(f"    错误: {e}", "ERROR")
        else:
            self.log("  无滑块图，跳过 slide_match 测试", "WARN")
            
        self.results["simple_true_result"] = results_simple_true
        self.results["simple_false_result"] = results_simple_false
        
        # 确定最佳结果
        best_result = results_simple_true or results_simple_false
        if best_result and "target" in best_result:
            x1, y1, x2, y2 = best_result["target"]
            self.log(f"\n  识别结果: x1={x1}, y1={y1}, x2={x2}, y2={y2}")
            self.log(f"  缺口宽度: {x2-x1}px, 高度: {y2-y1}px")
            self.log(f"  中心点 X: {(x1+x2)//2}")
            self.log(f"  左边缘 X: {x1}")
            
            # 保存标记图
            marked = bg_img.copy()
            cv2.rectangle(marked, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.line(marked, ((x1+x2)//2, 0), ((x1+x2)//2, bg_h), (0, 0, 255), 2)  # 中心线
            cv2.line(marked, (x1, 0), (x1, bg_h), (255, 0, 0), 1)  # 左边缘线
            cv2.imwrite(f"{self.debug_dir}/ddddocr_result.png", marked)
            self.log(f"  已保存结果图: {self.debug_dir}/ddddocr_result.png")
            
        return best_result
    
    def verify_coordinate_conversion(self, offset: int, img_w: int, 
                                      bg_css_w: float, slider_box: dict, bg_box: dict):
        """验证坐标转换逻辑"""
        self.log("\n验证坐标转换...")
        
        # 当前代码的计算方式
        scale_ratio = bg_css_w / img_w
        self.log(f"  缩放比例: {scale_ratio:.4f} (CSS宽度 {bg_css_w} / 截图宽度 {img_w})")
        
        # 使用中心点
        gap_center_css = offset * scale_ratio
        self.log(f"  缺口中心 CSS 坐标: {gap_center_css:.2f}px")
        
        # 使用左边缘（如果 offset 是中心点，需要调整）
        gap_left_css = (offset - 25) * scale_ratio if offset > 25 else offset * scale_ratio
        self.log(f"  缺口左边缘 CSS 坐标（估算）: {gap_left_css:.2f}px")
        
        # 当前代码的拖动距离计算
        gap_absolute_x = bg_box['x'] + gap_center_css
        slider_center_x = slider_box['x'] + slider_box['width'] / 2
        drag_distance_current = gap_absolute_x - slider_center_x
        
        self.log(f"\n  当前代码计算方式:")
        self.log(f"    缺口绝对 X = bg_box.x({bg_box['x']}) + gap_css({gap_center_css:.1f}) = {gap_absolute_x:.1f}")
        self.log(f"    滑块中心 X = slider_box.x({slider_box['x']}) + width/2({slider_box['width']/2}) = {slider_center_x:.1f}")
        self.log(f"    拖动距离 = {drag_distance_current:.1f}px")
        
        # 建议的计算方式：直接使用相对坐标
        # 假设滑块初始位置在背景图 x=0
        drag_distance_simple = gap_center_css
        self.log(f"\n  简化计算方式（假设滑块初始在 x=0）:")
        self.log(f"    拖动距离 = offset({offset}) * scale({scale_ratio:.3f}) = {drag_distance_simple:.1f}px")
        
        self.results["drag_distance_current"] = drag_distance_current
        self.results["drag_distance_simple"] = drag_distance_simple
        self.results["scale_ratio"] = scale_ratio


async def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_dir = f"verify_output_{timestamp}"
    os.makedirs(debug_dir, exist_ok=True)
    print(f"📁 输出目录: {debug_dir}\n")
    
    verifier = CaptchaVerifier(debug_dir)
    
    async with async_playwright() as p:
        # 注意：强制 DPR=1 避免缩放问题
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            device_scale_factor=1
        )
        page = await context.new_page()
        
        # 获取实际 DPR
        actual_dpr = await page.evaluate("window.devicePixelRatio")
        verifier.log(f"浏览器 DPR: {actual_dpr}")

        verifier.log("\n1️⃣ 导航到登录页...")
        await page.goto("https://passport.ctrip.com/user/login")
        await asyncio.sleep(2)

        # 触发验证码
        verifier.log("2️⃣ 触发验证码...")
        for txt in ["验证码登录", "手机号查单"]:
            if await page.is_visible(f"text='{txt}'"):
                await page.click(f"text='{txt}'")
                await asyncio.sleep(0.5)
                break

        await page.fill("input[type='tel']", "18888888888")
        await page.click("text='发送验证码'")

        # 等待验证码
        verifier.log("3️⃣ 等待滑块验证码...")
        try:
            await page.wait_for_selector(".cpt-drop-btn", timeout=10000)
        except:
            verifier.log("未检测到滑块验证码", "ERROR")
            await browser.close()
            return

        await asyncio.sleep(1.5)

        # 验证选择器
        verifier.log("\n4️⃣ 验证元素选择器...")

        bg_selectors = [
            ("img.advise", "主要背景图选择器"),
            (".cpt-img-cal-box img", "容器内图片"),
            (".cpt-bg-img img", "背景图容器"),
        ]

        bg_img_loc = None
        bg_selector_used = None
        for sel, desc in bg_selectors:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    box = await loc.bounding_box()
                    if box and box['width'] > 100:
                        verifier.log(f"  ✅ {sel} ({desc}): {box['width']}x{box['height']}", "OK")
                        bg_img_loc = loc
                        bg_selector_used = sel
                        break
                    else:
                        verifier.log(f"  ⚠️ {sel}: 尺寸太小 {box}", "WARN")
                else:
                    verifier.log(f"  ❌ {sel}: 不可见或不存在")
            except Exception as e:
                verifier.log(f"  ❌ {sel}: {e}", "ERROR")

        slider_piece_selectors = [
            (".cpt-img-double img", "滑块拼图"),
            (".cpt-small-img img", "小滑块图"),
            ("[class*='slider'] img", "通用滑块"),
        ]

        slider_piece_loc = None
        for sel, desc in slider_piece_selectors:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    box = await loc.bounding_box()
                    verifier.log(f"  ✅ {sel} ({desc}): {box['width']}x{box['height']}", "OK")
                    slider_piece_loc = loc
                    break
                else:
                    verifier.log(f"  ❌ {sel}: 不可见或不存在")
            except Exception as e:
                verifier.log(f"  ❌ {sel}: {e}")

        if not bg_img_loc:
            verifier.log("无法找到背景图！", "ERROR")
            await browser.close()
            return

        # 获取图片信息
        verifier.log("\n5️⃣ 获取图片详细信息...")
        img_info = await page.evaluate(f"""() => {{
            const img = document.querySelector('{bg_selector_used}');
            if (img) {{
                return {{
                    src_type: img.src.startsWith('data:') ? 'base64' : 'url',
                    naturalWidth: img.naturalWidth,
                    naturalHeight: img.naturalHeight,
                    displayWidth: img.clientWidth,
                    displayHeight: img.clientHeight,
                    complete: img.complete
                }};
            }}
            return null;
        }}""")
        verifier.log(f"  背景图信息: {img_info}")

        # 截图
        verifier.log("\n6️⃣ 截取图片...")
        bg_bytes = await bg_img_loc.screenshot()
        with open(f"{debug_dir}/bg_screenshot.png", "wb") as f:
            f.write(bg_bytes)
        verifier.log(f"  背景图截图: {len(bg_bytes)} bytes")

        slider_bytes = None
        if slider_piece_loc:
            slider_bytes = await slider_piece_loc.screenshot()
            with open(f"{debug_dir}/slider_screenshot.png", "wb") as f:
                f.write(slider_bytes)
            verifier.log(f"  滑块图截图: {len(slider_bytes)} bytes")
        else:
            # Fallback: 使用滑块按钮截图
            verifier.log("  ⚠️ 未找到滑块拼图，使用滑块按钮作为替代", "WARN")
            btn_loc = page.locator(".cpt-drop-btn").first
            slider_bytes = await btn_loc.screenshot()
            with open(f"{debug_dir}/slider_btn_screenshot.png", "wb") as f:
                f.write(slider_bytes)

        # 验证 ddddocr
        verifier.log("\n7️⃣ 验证 ddddocr 识别...")
        result = verifier.verify_ddddocr_params(bg_bytes, slider_bytes)

        # 验证坐标转换
        if result and "target" in result:
            verifier.log("\n8️⃣ 验证坐标转换...")
            x1, y1, x2, y2 = result["target"]
            offset = (x1 + x2) // 2  # 当前代码使用中心点

            bg_box = await bg_img_loc.bounding_box()
            slider_box = await page.locator(".cpt-drop-btn").bounding_box()

            bg_arr = np.frombuffer(bg_bytes, np.uint8)
            bg_img = cv2.imdecode(bg_arr, cv2.IMREAD_COLOR)
            img_w = bg_img.shape[1]

            verifier.verify_coordinate_conversion(
                offset, img_w, bg_box['width'], slider_box, bg_box
            )

            # 额外验证：使用 x1（左边缘）而不是中心点
            verifier.log("\n9️⃣ 对比两种计算方式...")
            scale = bg_box['width'] / img_w

            drag_with_center = offset * scale
            drag_with_left_edge = x1 * scale

            verifier.log(f"  使用中心点 (x1+x2)/2={offset}: 拖动 {drag_with_center:.1f}px")
            verifier.log(f"  使用左边缘 x1={x1}: 拖动 {drag_with_left_edge:.1f}px")
            verifier.log(f"  差异: {abs(drag_with_center - drag_with_left_edge):.1f}px")

            if abs(drag_with_center - drag_with_left_edge) > 15:
                verifier.log("  ⚠️ 差异较大，建议使用左边缘 x1 进行计算", "WARN")

        # 总结
        verifier.log("\n" + "="*50)
        verifier.log("📊 验证总结")
        verifier.log("="*50)

        if not result:
            verifier.log("❌ ddddocr 识别失败 - 需要检查图片质量", "ERROR")
        elif "target" not in result:
            verifier.log("❌ ddddocr 未返回目标位置", "ERROR")
        else:
            verifier.log("✅ ddddocr 识别成功", "OK")
            verifier.log(f"   建议拖动距离: {drag_with_left_edge:.1f}px（使用左边缘）")

        verifier.log(f"\n📁 调试文件已保存到: {debug_dir}/")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

