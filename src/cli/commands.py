"""CLI主入口

集成所有命令模块。
"""

import argparse
import sys

from src.cli.module_commands import setup_module_parser


def main():
    """CLI主入口"""
    parser = argparse.ArgumentParser(
        prog="crawler4j",
        description="Crawler4j 命令行工具",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 注册模块命令
    setup_module_parser(subparsers)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # 处理模块子命令
    if args.command == "module":
        if not hasattr(args, "func") or not args.func:
            # 显示模块命令帮助
            parser.parse_args(["module", "--help"])
            return 0
        return args.func(args)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
