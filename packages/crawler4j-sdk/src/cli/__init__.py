"""CLI 命令模块。"""

from __future__ import annotations


def main() -> int:
    """惰性导入 CLI 入口，避免 `python -m ...commands` 时重复预加载。"""
    from crawler4j_sdk.cli.commands import main as commands_main

    return commands_main()


__all__ = ["main"]
