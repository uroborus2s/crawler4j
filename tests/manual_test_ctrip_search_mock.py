import asyncio
import os
import sys

# 将 src 目录添加到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, timedelta

from playwright.async_api import async_playwright

from src.automation.workflows.ctrip_search import CtripSearchWorkflow
from src.core.browser_api import BrowserAPI
from src.core.models.labor_task import LaborTask, TaskState
from src.utils.logger import logger

# ==================== 测试配置 ====================
# 如果您想在特定环境（带登录状态）运行，请填写环境 ID
PROFILE_ID = ""  # 例如 "1" 或您的指纹浏览器 ID

# 如果您想链接本地已打开的 Chrome 浏览器，请先启动 Chrome：
# /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
USE_LOCAL_CHROME = True  # 设置为 True 则链接本地 9222 端口的 Chrome
# =================================================

async def run_mock_test():
    """使用模拟数据运行携程搜索测试。"""
    async with async_playwright() as p:
        browser = None
        
        if USE_LOCAL_CHROME:
            logger.info("🚀 正在链接本地 Chrome 浏览器 (127.0.0.1:9222)...")
            
            # 设置环境变量绕过本地代理
            os.environ["NO_PROXY"] = "127.0.0.1,localhost"
            
            try:
                import requests
                ws_url = None
                try:
                    version_url = "http://127.0.0.1:9222/json/version"
                    # 禁用代理，直接访问本地
                    resp = requests.get(version_url, timeout=5, proxies={"http": "", "https": ""})
                    if resp.status_code == 200:
                        ws_url = resp.json().get("webSocketDebuggerUrl")
                        if ws_url:
                            logger.info(f"📍 发现 WebSocket URL: {ws_url}")
                    else:
                        logger.error(f"❌ 访问 /json/version 返回状态码 {resp.status_code}: {resp.text}")
                except Exception as e:
                    logger.warning(f"⚠️ 手动发现 WS 失败: {e}")
                
                # 如果发现了 ws_url，直接连接；否则尝试使用调试地址连接
                endpoint = ws_url if ws_url else "http://127.0.0.1:9222"
                browser = await p.chromium.connect_over_cdp(endpoint)
                
                if not browser:
                    logger.error("❌ 浏览器连接对象为空")
                    return
                
                if browser.contexts:
                    context = browser.contexts[0]
                else:
                    context = await browser.new_context()
                page = await context.new_page()
                logger.info("✅ 已成功链接本地 Chrome")
            except Exception as e:
                logger.error(f"❌ 无法链接到本地 Chrome: {e}")
                logger.info("💡 诊断建议：\n1. 请在浏览器打开 http://127.0.0.1:9222/json/version 检查是否显示 JSON\n2. 确保没有其他 Chrome 进程或代理软件干扰 9222 端口\n3. 尝试完全退出 Chrome 后再次启动")
                return
        elif PROFILE_ID:
            try:
                # 获取环境连接信息
                res = BrowserAPI.open_browser(PROFILE_ID)
                ws_url = res.get("ws_endpoint")
                
                if not ws_url:
                    logger.error(f"❌ 环境 {PROFILE_ID} 未返回有效的 WebSocket 地址")
                    return

                # 连接到已存在的指纹浏览器环境
                browser = await p.chromium.connect_over_cdp(ws_url)
                # 获取已有的上下文或新建
                if browser.contexts:
                    context = browser.contexts[0]
                else:
                    context = await browser.new_context()
                
                page = await context.new_page()
                logger.info("✅ 已成功连接并接管指纹浏览器环境")
            except Exception as e:
                logger.error(f"❌ 无法连接到环境 {PROFILE_ID}: {e}")
                return
        else:
            # 方案二：启动纯净浏览器
            logger.info("🚀 启动纯净 Chromium 浏览器执行测试...")
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(viewport={'width': 1280, 'height': 800})
            page = await context.new_page()

        # 1. 模拟一个任务数据
        # 使用一个真实的酒店以便测试搜索结果
        today = datetime.now()
        checkin = (today + timedelta(days=4)).strftime("%Y-%m-%d")
        checkout = (today + timedelta(days=5)).strftime("%Y-%m-%d")
        
        mock_task = LaborTask(
            hotel_name="上海衡山花园酒店",
            city_name="上海",
            checkin=checkin,
            checkout=checkout,
            state=TaskState.COMPLETE
        )
        
        logger.info(f"🧪 开始模拟测试，任务数据: {mock_task}")

        # 2. 初始化携程搜索工作流
        workflow = CtripSearchWorkflow(page)
        
        # 3. 执行搜索与采集
        try:
            result = await workflow.search_and_capture(mock_task)
            
            if result:
                logger.info("✅ 模拟测试成功！抓取到的数据摘要:")
                # 打印部分数据
                if isinstance(result, dict):
                    # 根据实际捕获的 JSON 结构解析
                    logger.info(f"抓取到的数据键值: {list(result.keys())[:5]}")
            else:
                logger.error("❌ 模拟测试失败，未能截获数据")
                
        except Exception as e:
            logger.error(f"💥 测试过程中发生异常: {e}")
        finally:
            logger.info("测试结束，5秒后关闭浏览器...")
            await asyncio.sleep(5)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_mock_test())
