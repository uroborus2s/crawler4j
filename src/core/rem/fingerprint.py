"""指纹配置抽象模块。

设计参考: docs/design/module-01-runtime-environment.md §5.4

提供指纹浏览器配置的统一抽象：
    - FingerprintProvider: 指纹配置协议
"""

from typing import Any, Protocol


class FingerprintProvider(Protocol):
    """指纹配置协议。
    
    设计文档 5.4: 统一 BitBrowser/VirtualBrowser 指纹接口
    
    实现此协议的 Provider 可以支持指纹管理功能。
    """
    
    async def randomize_fingerprint(self, env_id: str) -> bool:
        """随机化环境指纹。
        
        Args:
            env_id: 环境 ID（内部 ID 或 external_id）
            
        Returns:
            是否成功
        """
        ...
    
    async def get_fingerprint(self, env_id: str) -> dict[str, Any]:
        """获取环境当前指纹配置。
        
        Args:
            env_id: 环境 ID
            
        Returns:
            指纹配置字典，包含以下可能的字段：
                - user_agent: str
                - resolution: str (如 "1920x1080")
                - timezone: str
                - language: str
                - webgl_vendor: str
                - webgl_renderer: str
                - canvas_noise: bool
                - hardware_concurrency: int
        """
        ...
    
    async def update_fingerprint(self, env_id: str, config: dict[str, Any]) -> bool:
        """更新环境指纹配置。
        
        Args:
            env_id: 环境 ID
            config: 指纹配置字典
            
        Returns:
            是否成功
        """
        ...


class FingerprintNotSupportedError(Exception):
    """Provider 不支持指纹管理。"""
    pass


def supports_fingerprint(provider: object) -> bool:
    """检查 Provider 是否支持指纹管理。
    
    Args:
        provider: Provider 实例
        
    Returns:
        是否支持指纹管理
    """
    return (
        hasattr(provider, "randomize_fingerprint") and
        hasattr(provider, "get_fingerprint") and
        hasattr(provider, "update_fingerprint")
    )
