"""外部应用管理服务。

负责检测和启动外部指纹浏览器软件（BitBrowser / VirtualBrowser）。

职责:
1. 检测应用运行状态 (is_running)
2. 启动应用 (launch)
3. 等待应用就绪 (wait_until_ready)
4. 确保应用运行 (ensure_running = 检测 + 启动 + 等待)
"""

from __future__ import annotations

import asyncio
import os
import platform
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.core.foundation.logging import logger


class ExternalApp(str, Enum):
    """支持的外部应用枚举。"""
    BITBROWSER = "bitbrowser"
    VIRTUALBROWSER = "virtualbrowser"


@dataclass
class AppLaunchResult:
    """应用启动结果。"""
    success: bool
    error_code: str = ""  # PATH_NOT_CONFIGURED, PATH_NOT_FOUND, LAUNCH_FAILED, TIMEOUT
    error_message: str = ""


# 应用配置映射
APP_CONFIG: dict[ExternalApp, dict[str, Any]] = {
    ExternalApp.BITBROWSER: {
        "config_key_path": "browser.bitbrowser.path",
        "config_key_port": "browser.bitbrowser.port",
        "default_port": 54345,
        "display_name": "BitBrowser",
        "process_names": {
            "Darwin": ["BitBrowser"],
            "Windows": ["BitBrowser.exe"],
        },
        "app_names": {
            "Darwin": "BitBrowser",  # 用于 open -a
        },
        # 平台默认安装路径
        "default_paths": {
            "Darwin": "/Applications/比特浏览器.app",
            "Windows": "",  # Windows 安装路径不固定，需用户配置
        },
    },
    ExternalApp.VIRTUALBROWSER: {
        "config_key_path": "browser.virtualbrowser.path",
        "config_key_port": "browser.virtualbrowser.port",
        "default_port": 9002,
        "display_name": "VirtualBrowser",
        "process_names": {
            "Darwin": ["VirtualBrowser", "virtual-browser"],
            "Windows": ["VirtualBrowser.exe"],
        },
        "app_names": {
            "Darwin": "VirtualBrowser",
        },
        "default_paths": {
            "Darwin": "/Applications/VirtualBrowser.app",
            "Windows": "",
        },
    },
}


class ExternalAppService:
    """外部应用管理服务。
    
    跨平台支持 macOS 和 Windows。
    """
    
    def __init__(self):
        self._system = platform.system()  # "Darwin" or "Windows"
    
    async def is_running(self, app: ExternalApp | str) -> bool:
        """检测应用是否运行中。
        
        策略: 优先通过 API 端口检测（更可靠），回退到进程检测。
        
        Args:
            app: 应用标识
            
        Returns:
            是否运行中
        """
        app_enum = ExternalApp(app) if isinstance(app, str) else app
        config = APP_CONFIG[app_enum]
        
        # 方式1: 尝试连接 API 端口
        port = self._get_app_port(app_enum)
        if await self._check_port_available(port):
            logger.debug(f"[ExternalApp] {app_enum.value} 检测到 API 端口 {port} 可用")
            return True
        
        # 方式2: 进程名检测
        process_names = config["process_names"].get(self._system, [])
        for proc_name in process_names:
            if await self._check_process_running(proc_name):
                logger.debug(f"[ExternalApp] {app_enum.value} 检测到进程 {proc_name} 运行中")
                return True
        
        return False
    
    async def launch(self, app: ExternalApp | str, app_path: str) -> bool:
        """启动应用。
        
        Args:
            app: 应用标识
            app_path: 应用路径（已验证存在）
            
        Returns:
            是否启动成功
        """
        app_enum = ExternalApp(app) if isinstance(app, str) else app
        config = APP_CONFIG[app_enum]
        
        try:
            if self._system == "Darwin":
                return await self._launch_macos(app_enum, app_path, config)
            elif self._system == "Windows":
                return await self._launch_windows(app_path)
            else:
                logger.error(f"[ExternalApp] 不支持的操作系统: {self._system}")
                return False
        except Exception as e:
            logger.error(f"[ExternalApp] 启动 {app_enum.value} 失败: {e}")
            return False
    
    async def wait_until_ready(
        self, 
        app: ExternalApp | str, 
        timeout: int = 30
    ) -> bool:
        """等待应用 API 就绪。
        
        Args:
            app: 应用标识
            timeout: 超时时间（秒）
            
        Returns:
            是否就绪
        """
        app_enum = ExternalApp(app) if isinstance(app, str) else app
        port = self._get_app_port(app_enum)
        
        logger.info(f"[ExternalApp] 等待 {app_enum.value} API 就绪 (端口 {port})...")
        
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            if await self._check_app_api_ready(app_enum, port):
                logger.info(f"[ExternalApp] {app_enum.value} API 已就绪")
                return True
            await asyncio.sleep(1)
        
        logger.error(f"[ExternalApp] {app_enum.value} API 等待超时 ({timeout}s)")
        return False
    
    async def ensure_running(
        self, 
        app: ExternalApp | str,
        timeout: int = 30
    ) -> AppLaunchResult:
        """确保应用运行（检测 -> 启动 -> 等待就绪）。
        
        这是 Provider 层调用的主入口方法。
        
        Args:
            app: 应用标识
            timeout: 等待就绪超时时间
            
        Returns:
            AppLaunchResult 包含成功/失败状态和错误信息
        """
        app_enum = ExternalApp(app) if isinstance(app, str) else app
        config = APP_CONFIG[app_enum]
        display_name = config.get("display_name", app_enum.value)
        
        # 1. 检测是否已运行
        if await self.is_running(app_enum):
            logger.info(f"[ExternalApp] {display_name} 已在运行")
            if await self.wait_until_ready(app_enum, timeout=timeout):
                return AppLaunchResult(success=True)
            msg = f"{display_name} API 等待超时 ({timeout}秒)，请手动检查应用是否正常运行"
            logger.error(f"[ExternalApp] {msg}")
            return AppLaunchResult(
                success=False,
                error_code="TIMEOUT",
                error_message=msg
            )
        
        # 2. 获取并验证应用路径
        app_path = self._get_app_path(app_enum)
        
        if not app_path:
            msg = f"{display_name} 安装路径未配置，请在「配置中心 → 外部浏览器」中配置应用路径"
            logger.error(f"[ExternalApp] {msg}")
            return AppLaunchResult(
                success=False,
                error_code="PATH_NOT_CONFIGURED",
                error_message=msg
            )
        
        # 3. 验证路径是否存在
        if not os.path.exists(app_path):
            msg = f"{display_name} 安装路径不存在: {app_path}"
            logger.error(f"[ExternalApp] {msg}")
            return AppLaunchResult(
                success=False,
                error_code="PATH_NOT_FOUND",
                error_message=msg
            )
        
        # 4. 尝试启动
        logger.info(f"[ExternalApp] {display_name} 未运行，尝试启动: {app_path}")
        
        if not await self.launch(app_enum, app_path):
            msg = f"{display_name} 启动失败，请检查应用是否可以正常打开"
            logger.error(f"[ExternalApp] {msg}")
            return AppLaunchResult(
                success=False,
                error_code="LAUNCH_FAILED",
                error_message=msg
            )
        
        # 5. 等待就绪
        if not await self.wait_until_ready(app_enum, timeout=timeout):
            msg = f"{display_name} 启动超时 ({timeout}秒)，请手动检查应用是否正常运行"
            logger.error(f"[ExternalApp] {msg}")
            return AppLaunchResult(
                success=False,
                error_code="TIMEOUT",
                error_message=msg
            )
        
        return AppLaunchResult(success=True)
    
    # =========================================================================
    # 私有方法
    # =========================================================================
    
    def _get_app_path(self, app: ExternalApp) -> str:
        """从配置中心获取应用路径，未配置时使用平台默认值。
        
        优先级:
        1. 用户配置的路径
        2. 平台默认安装路径 (APP_CONFIG.default_paths)
        """
        from src.core.system.config_center import get_config_center
        
        config = APP_CONFIG[app]
        config_center = get_config_center()
        
        # 1. 用户配置优先
        user_path = config_center.get(config["config_key_path"])
        if user_path:
            return user_path
        
        # 2. 回退到平台默认路径
        default_paths = config.get("default_paths", {})
        return default_paths.get(self._system, "")

    
    def _get_app_port(self, app: ExternalApp) -> int:
        """从配置中心获取应用 API 端口。"""
        from src.core.system.config_center import get_config_center
        
        config = APP_CONFIG[app]
        return int(get_config_center().get(config["config_key_port"]))

    async def _check_app_api_ready(self, app: ExternalApp, port: int) -> bool:
        """检查应用管理 API 是否达到可执行业务接口的就绪状态。"""
        if app == ExternalApp.VIRTUALBROWSER:
            return await self._check_virtualbrowser_api_ready(port)
        return await self._check_port_available(port)

    async def _check_virtualbrowser_api_ready(self, port: int) -> bool:
        """通过 VirtualBrowser 管理接口判断真实就绪，避免端口刚监听就创建环境。"""
        import httpx

        from src.core.system.config_center import get_config_center

        api_key = str(get_config_center().get("browser.virtualbrowser.apikey") or "").strip()
        headers = {"api-key": api_key} if api_key else {}
        url = f"http://127.0.0.1:{port}/api/getBrowserList"

        try:
            async with httpx.AsyncClient(timeout=2.0, headers=headers, trust_env=False) as client:
                resp = await client.get(url)
            body = (resp.text or "").strip()
            try:
                data = resp.json()
            except Exception:
                data = None
            if resp.is_success and isinstance(data, dict) and data.get("success") is True:
                return True
            logger.debug(
                f"[ExternalApp] virtualbrowser API 未就绪: status={resp.status_code} body={body[:300]}"
            )
            return False
        except httpx.ConnectError:
            return False
        except httpx.ReadTimeout:
            return False
        except Exception as e:
            logger.debug(f"[ExternalApp] virtualbrowser API 就绪检测失败: {e}")
            return False
    
    async def _check_port_available(self, port: int) -> bool:
        """检查端口是否有目标服务响应。
        
        策略:
        - 2xx/3xx/4xx → 服务运行中（4xx 只是路径不存在）
        - 5xx → 服务异常（可能是代理转发但后端未启动）
        - ConnectError → 端口无服务
        """
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
                resp = await client.get(f"http://127.0.0.1:{port}/")
                return resp.status_code < 500
        except httpx.ConnectError:
            return False
        except httpx.ReadTimeout:
            # 读取超时 = 服务可能在启动中，保守视为未就绪
            return False
        except Exception:
            return False
    
    async def _check_process_running(self, process_name: str) -> bool:
        """检查进程是否运行。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            self._check_process_running_sync, 
            process_name
        )
    
    def _check_process_running_sync(self, process_name: str) -> bool:
        """同步检查进程（在线程池中执行）。"""
        try:
            if self._system == "Darwin":
                result = subprocess.run(
                    ["pgrep", "-x", process_name],  # -x 精确匹配进程名
                    capture_output=True,
                    timeout=5
                )
                return result.returncode == 0
            elif self._system == "Windows":
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                return process_name.lower() in result.stdout.lower()
            return False
        except Exception:
            return False
    
    async def _launch_macos(
        self, 
        app: ExternalApp, 
        app_path: str, 
        config: dict
    ) -> bool:
        """macOS 启动应用。"""
        loop = asyncio.get_event_loop()
        
        def _launch() -> bool:
            try:
                if app_path.endswith(".app"):
                    # 使用 open 命令打开 .app 包
                    result = subprocess.run(
                        ["open", app_path],
                        capture_output=True,
                        timeout=10
                    )
                    if result.returncode != 0:
                        stderr = result.stderr.decode() if result.stderr else ""
                        logger.error(f"[ExternalApp] open 命令失败: {stderr}")
                        return False
                    return True
                else:
                    # 直接执行可执行文件
                    subprocess.Popen(
                        [app_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    return True
            except subprocess.TimeoutExpired:
                logger.error("[ExternalApp] 启动命令超时")
                return False
            except Exception as e:
                logger.error(f"[ExternalApp] 启动命令异常: {e}")
                return False
        
        return await loop.run_in_executor(None, _launch)
    
    async def _launch_windows(self, app_path: str) -> bool:
        """Windows 启动应用。"""
        loop = asyncio.get_event_loop()
        
        def _launch() -> bool:
            try:
                # Windows: 设置 cwd 确保 DLL 依赖能正确加载
                subprocess.Popen(
                    [app_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=os.path.dirname(app_path),
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW  # type: ignore
                )
                return True
            except Exception as e:
                logger.error(f"[ExternalApp] Windows 启动异常: {e}")
                return False
        
        return await loop.run_in_executor(None, _launch)


# 单例
_external_app_service: ExternalAppService | None = None


def get_external_app_service() -> ExternalAppService:
    """获取 ExternalAppService 单例。"""
    global _external_app_service
    if _external_app_service is None:
        _external_app_service = ExternalAppService()
    return _external_app_service
